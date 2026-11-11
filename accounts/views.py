import logging

from django.db.models import Count
from django.db.models.functions import TruncDate
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from jobs.models import Application, Job

from .models import (
    AdminActionLog,
    AuditTrail,
    CandidateProfile,
    EmployerProfile,
    User,
)
from .permissions import (
    IsAdmin,
    IsCandidate,
    IsEmployer,
)
from .response import success_response
from .serializers import (
    EmployerProfileSerializer,
    ResumeUploadSerializer,
    SignupSerializer,
    UserListSerializer,
)
from .services.resume_nlp import parse_resume
from .services.resume_parser import extract_resume_text


# Add the new class here
@extend_schema(
    summary="Refresh JWT access tokens.",
    description="Generate a new access token using a valid refresh token.",
)
class DocumentedTokenRefreshView(TokenRefreshView):
    pass


logger = logging.getLogger("accounts")
ai_logger = logging.getLogger("ai_events")

def record_security_event(request, action, description):
    user = request.user
    actor = user if user.is_authenticated else None

    AuditTrail.objects.create(
        actor=actor,
        category="SECURITY",
        action=action,
        description=description,
        metadata={
            "path": request.path,
            "method": request.method,
        },
    )


class LoginRateThrottle(AnonRateThrottle):
    scope = "login"


class CustomTokenObtainPairView(TokenObtainPairView):
    throttle_classes = [LoginRateThrottle]

    @extend_schema(
        summary="Authenticate a user and obtain JWT tokens.",
        description="Authenticate a user and obtain JWT access and refresh tokens.",
        responses={200: dict, 401: dict},
        tags=["Authentication"],
    )
    def post(self, request, *args, **kwargs):
        # Keep your existing method implementation unchanged
        try:
            response = super().post(request, *args, **kwargs)
            return response
        except AuthenticationFailed:
            logger.warning(
                "Failed login attempt from IP=%s",
                request.META.get("REMOTE_ADDR", "unknown"),
            )
            record_security_event(
                request,
                action="LOGIN_FAILED",
                description="Login failed due to invalid credentials.",
            )
            raise


class SignupAPIView(APIView):

    permission_classes = [AllowAny]

    @extend_schema(
        summary="Register a new user account.",
        request=SignupSerializer,
        responses={201: dict, 400: dict},
        description="Register a new user account.",
        tags=["Authentication"],
    )
    def post(self, request):

        serializer = SignupSerializer(data=request.data)

        if serializer.is_valid():

            user = serializer.save()

            return success_response(
                message="User created successfully.",
                data={
                    "id": user.id,
                    "email": user.email,
                    "username": user.username,
                    "phone": user.phone,
                    "role": user.role,
                    "is_verified": user.is_verified,
                },
                status_code=status.HTTP_201_CREATED,
            )

        return Response(
            {
                "success": False,
                "status_code": status.HTTP_400_BAD_REQUEST,
                "errors": serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )


class ProfileAPIView(APIView):

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Retrieve the authenticated user's profile.",
        responses={200: dict},
        description="Retrieve the authenticated user's profile.",
        tags=["User Profile"],
    )
    def get(self, request):

        user = request.user

        return success_response(
            message="Profile fetched successfully.",
            data={
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "phone": user.phone,
                "role": user.role,
                "is_verified": user.is_verified,
            },
            status_code=status.HTTP_200_OK,
        )


class EmployerProfileAPIView(APIView):

    permission_classes = [IsEmployer]

    @extend_schema(
        summary="Create or update the employer company profile.",
        request=EmployerProfileSerializer,
        responses={201: EmployerProfileSerializer, 400: dict},
        description="Create an employer profile for the authenticated employer.",
        tags=["Employer Profile"],
    )
    def post(self, request):

        if EmployerProfile.objects.filter(user=request.user).exists():

            return Response(
                {
                    "success": False,
                    "status_code": status.HTTP_400_BAD_REQUEST,
                    "errors": {
                        "detail": "Employer profile already exists."
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = EmployerProfileSerializer(data=request.data)

        if serializer.is_valid():

            serializer.save(user=request.user)

            return success_response(
                message="Employer profile created successfully.",
                data=serializer.data,
                status_code=status.HTTP_201_CREATED,
            )

        return Response(
            {
                "success": False,
                "status_code": status.HTTP_400_BAD_REQUEST,
                "errors": serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )


class ResumeUploadAPIView(APIView):

    permission_classes = [IsCandidate]

    @extend_schema(
        summary="Upload and analyze a candidate resume.",
        request=ResumeUploadSerializer,
        responses={
            200: dict,
            400: dict,
            404: dict,
            500: dict,
        },
        description=(
            "Upload a PDF or DOCX resume (maximum 5 MB). "
            "The system extracts text and performs AI resume analysis."
        ),
        tags=["Resume Management"],
    )
    def post(self, request):

        try:
            profile = CandidateProfile.objects.get(
                user=request.user
            )

        except CandidateProfile.DoesNotExist:

            return Response(
                {
                    "success": False,
                    "status_code": status.HTTP_404_NOT_FOUND,
                    "errors": {
                        "detail": "Candidate profile not found."
                    },
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ResumeUploadSerializer(
            profile,
            data=request.data,
            partial=True,
        )

        if not serializer.is_valid():

            return Response(
                {
                    "success": False,
                    "status_code": status.HTTP_400_BAD_REQUEST,
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer.save()

        resume_file = profile.resume

        try:
            resume_file.open("rb")

            extracted_text = extract_resume_text(
                resume_file.file
            )

            resume_file.close()

        except ValueError as e:

            return Response(
                {
                    "success": False,
                    "status_code": status.HTTP_400_BAD_REQUEST,
                    "errors": {
                        "detail": str(e)
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.exception(
                "Resume processing failed for user_id=%s",
                request.user.id,
            )

            AuditTrail.objects.create(
                actor=request.user,
                category="AI",
                action="RESUME_PROCESSING_FAILED",
                description="Resume processing failed.",
                target_type="CandidateProfile",
                target_id=str(profile.id),
                metadata={
                    "user_id": request.user.id,
                    "error_type": "resume_processing_error",
                },
            )
            return Response(
                {
                    "success": False,
                    "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "errors": {
                        "detail": "Unable to parse resume.",
                        "error": "Internal resume processing error.",
                    },
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        parsed_resume = parse_resume(extracted_text)

        ai_logger.info(
            "Resume analyzed successfully for user_id=%s",
            request.user.id,
        )

        AuditTrail.objects.create(
            actor=request.user,
            category="AI",
            action="RESUME_ANALYZED",
            description="Resume text extracted and analyzed.",
            target_type="CandidateProfile",
            target_id=str(profile.id),
            metadata={
                "user_id": request.user.id,
            },
        )

        return success_response(
            message="Resume uploaded and analyzed successfully.",
            data={
                "resume": serializer.data["resume"],
                "extracted_text": extracted_text,
                "parsed_resume": parsed_resume,
        },
        status_code=status.HTTP_200_OK,
        )


class EmployerDashboardAPIView(APIView):

    permission_classes = [IsEmployer]

    @extend_schema(
        summary="Retrieve the employer dashboard.",
        responses={
            200: dict,
        },
        description=(
            "Retrieve the employer dashboard with the authenticated "
            "user's ID, email, and role."
        ),
        tags=["Employer Dashboard"],
    )
    def get(self, request):

        return success_response(
            message="Employer dashboard loaded successfully.",
            data={
                "id": request.user.id,
                "email": request.user.email,
                "role": request.user.role,
            },
            status_code=status.HTTP_200_OK,
        )


class EmployerApprovalAPIView(APIView):

    permission_classes = [IsAdmin]

    @extend_schema(
        summary="Approve an employer account.",
        request=None,
        responses={
            200: dict,
            400: dict,
            404: dict,
        },
        description=(
            "Approve an employer profile using its user ID. "
            "Returns an error if the profile is not found or is already approved."
        ),
        tags=["Employer Management"],
    )
    def patch(self, request, user_id):

        try:
            employer = EmployerProfile.objects.get(
                user_id=user_id
            )

        except EmployerProfile.DoesNotExist:

            return Response(
                {
                    "success": False,
                    "status_code": status.HTTP_404_NOT_FOUND,
                    "errors": {
                        "detail": "Employer profile not found."
                    },
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if employer.is_company_verified:

            return Response(
                {
                    "success": False,
                    "status_code": status.HTTP_400_BAD_REQUEST,
                    "errors": {
                        "detail": "Employer is already approved."
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        employer.is_company_verified = True
        employer.save()

        AdminActionLog.objects.create(
            admin=request.user,
            action="EMPLOYER_APPROVED",
            target_user=employer.user,
            reason="Employer approved by admin.",
        )

        AuditTrail.objects.create(
            actor=request.user,
            category="ADMIN",
            action="EMPLOYER_APPROVED",
            description="Admin approved an employer.",
            target_type="EmployerProfile",
            target_id=str(employer.id),
            metadata={
                "target_user_id": employer.user_id,
            },
        )

        return success_response(
            message="Employer approved successfully.",
            data={
                "user_id": employer.user.id,
                "email": employer.user.email,
                "company_name": employer.company_name,
                "is_company_verified": employer.is_company_verified,
            },
            status_code=status.HTTP_200_OK,
        )


class UserBlockAPIView(APIView):

    permission_classes = [IsAdmin]

    @extend_schema(
        summary="Block a user account.",
        request=None,
        responses={
            200: dict,
            400: dict,
            404: dict,
        },
        description=(
            "Block a user account using its user ID. "
            "An administrator cannot block their own account or "
            "block an account that is already blocked."
        ),
        tags=["User Management"],
    )
    def patch(self, request, user_id):

        try:
            user = User.objects.get(id=user_id)

        except User.DoesNotExist:

            return Response(
                {
                    "success": False,
                    "status_code": status.HTTP_404_NOT_FOUND,
                    "errors": {
                        "detail": "User not found."
                    },
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if user.id == request.user.id:

            return Response(
                {
                    "success": False,
                    "status_code": status.HTTP_400_BAD_REQUEST,
                    "errors": {
                        "detail": "Admin cannot block their own account."
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not user.is_active:

            return Response(
                {
                    "success": False,
                    "status_code": status.HTTP_400_BAD_REQUEST,
                    "errors": {
                        "detail": "User is already blocked."
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.is_active = False
        user.save()

        AdminActionLog.objects.create(
            admin=request.user,
            action="USER_BLOCKED",
            target_user=user,
            reason="User blocked by admin.",
        )

        AuditTrail.objects.create(
            actor=request.user,
            category="ADMIN",
            action="USER_BLOCKED",
            description="Admin blocked a user.",
            target_type="User",
            target_id=str(user.id),
            metadata={
                "target_user_id": user.id,
            },
        )

        return success_response(
            message="User blocked successfully.",
            data={
                "id": user.id,
                "email": user.email,
                "role": user.role,
                "is_active": user.is_active,
            },
            status_code=status.HTTP_200_OK,
        )


class UserUnblockAPIView(APIView):

    permission_classes = [IsAdmin]

    @extend_schema(
        summary="Unblock a user account.",
        request=None,
        responses={
            200: dict,
            400: dict,
            404: dict,
        },
        description=(
            "Unblock a user account using its user ID. "
            "Returns an error if the user is not found or is already active."
        ),
        tags=["User Management"],
    )
    def patch(self, request, user_id):

        try:
            user = User.objects.get(id=user_id)

        except User.DoesNotExist:

            return Response(
                {
                    "success": False,
                    "status_code": status.HTTP_404_NOT_FOUND,
                    "errors": {
                        "detail": "User not found."
                    },
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if user.is_active:

            return Response(
                {
                    "success": False,
                    "status_code": status.HTTP_400_BAD_REQUEST,
                    "errors": {
                        "detail": "User is already active."
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.is_active = True
        user.save()

        AdminActionLog.objects.create(
            admin=request.user,
            action="USER_UNBLOCKED",
            target_user=user,
            reason="User unblocked by admin.",
        )

        AuditTrail.objects.create(
            actor=request.user,
            category="ADMIN",
            action="USER_UNBLOCKED",
            description="Admin unblocked a user.",
            target_type="User",
            target_id=str(user.id),
            metadata={
                "target_user_id": user.id,
            },
        )

        return success_response(
            message="User unblocked successfully.",
            data={
                "id": user.id,
                "email": user.email,
                "role": user.role,
                "is_active": user.is_active,
            },
            status_code=status.HTTP_200_OK,
        )

    
class CandidateDashboardAPIView(APIView):

    permission_classes = [IsCandidate]

    @extend_schema(
        summary="Retrieve the candidate dashboard.",
        responses={
            200: dict,
        },
        description=(
            "Retrieve the candidate dashboard with the authenticated "
            "user's ID, email, and role."
        ),
        tags=["Candidate Dashboard"],
    )
    def get(self, request):

        return success_response(
            message="Candidate dashboard loaded successfully.",
            data={
                "id": request.user.id,
                "email": request.user.email,
                "role": request.user.role,
            },
            status_code=status.HTTP_200_OK,
        )


class AdminDashboardAPIView(APIView):

    permission_classes = [IsAdmin]

    @extend_schema(
    summary="Retrieve the admin dashboard.",
    responses={200: dict},
    description=(
        "Retrieve platform-wide user, job, and application "
        "statistics for administrators."
    ),
    tags=["Admin Dashboard"],
    )
    def get(self, request):

        total_users = User.objects.count()

        active_users = User.objects.filter(
            is_active=True,
        ).count()

        blocked_users = User.objects.filter(
            is_active=False,
        ).count()

        total_employers = User.objects.filter(
            role="EMPLOYER",
        ).count()

        total_candidates = User.objects.filter(
            role="CANDIDATE",
        ).count()

        total_jobs = Job.objects.count()

        active_jobs = Job.objects.filter(
            is_active=True,
        ).count()

        inactive_jobs = Job.objects.filter(
            is_active=False,
        ).count()

        open_jobs = Job.objects.filter(
            status="OPEN",
            is_active=True,
        ).count()

        closed_jobs = Job.objects.filter(
            status="CLOSED",
        ).count()

        total_applications = Application.objects.count()

        return success_response(
            message="Admin dashboard statistics fetched successfully.",
            data={
                "users": {
                    "total": total_users,
                    "active": active_users,
                    "blocked": blocked_users,
                    "employers": total_employers,
                    "candidates": total_candidates,
                },
                "jobs": {
                    "total": total_jobs,
                    "active": active_jobs,
                    "inactive": inactive_jobs,
                    "open": open_jobs,
                    "closed": closed_jobs,
                },
                "applications": {
                    "total": total_applications,
                },
            },
            status_code=status.HTTP_200_OK,
        )


class AdminUserGrowthAPIView(APIView):

    permission_classes = [IsAdmin]

    @extend_schema(
    summary="Retrieve daily user growth statistics.",
    responses={200: dict},
    description=(
        "Retrieve daily user registration statistics, "
        "grouped by creation date."
    ),
    tags=["Admin Analytics"],
    )
    def get(self, request):

        growth = (
            User.objects
            .annotate(date=TruncDate("created_at"))
            .values("date")
            .annotate(users=Count("id"))
            .order_by("date")
        )

        return success_response(
            message="User growth statistics fetched successfully.",
            data={
                "daily_growth": list(growth),
            },
            status_code=status.HTTP_200_OK,
        )


class AdminJobActivityAPIView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
    summary="Retrieve job activity statistics.",
    responses={200: dict},
    description=(
        "Retrieve job activity statistics, including total, active, "
        "inactive, open, and closed jobs, with a breakdown by job type."
    ),
    tags=["Admin Analytics"],
    )
    def get(self, request):
        total_jobs = Job.objects.count()
        active_jobs = Job.objects.filter(is_active=True).count()
        inactive_jobs = Job.objects.filter(is_active=False).count()
        open_jobs = Job.objects.filter(status="OPEN").count()
        closed_jobs = Job.objects.filter(status="CLOSED").count()

        jobs_by_type = (
            Job.objects
            .values("job_type")
            .annotate(count=Count("id"))
            .order_by("job_type")
        )

        return success_response(
            message="Job activity statistics fetched successfully.",
            data={
                "total_jobs": total_jobs,
                "active_jobs": active_jobs,
                "inactive_jobs": inactive_jobs,
                "open_jobs": open_jobs,
                "closed_jobs": closed_jobs,
                "jobs_by_type": list(jobs_by_type),
            },
            status_code=status.HTTP_200_OK,
        )


class AdminUserFlagAPIView(APIView):

    permission_classes = [IsAdmin]

    @extend_schema(
        summary="Flag a user account for administrative review.",
        request=None,
        responses={
            200: dict,
            400: dict,
            404: dict,
        },
        description=(
            "Flag a user account using its user ID. "
            "An administrator cannot flag their own account or "
            "flag a user who is already flagged."
        ),
        tags=["User Management"],
    )
    def patch(self, request, user_id):

        try:
            user = User.objects.get(id=user_id)

        except User.DoesNotExist:

            return Response(
                {
                    "success": False,
                    "status_code": status.HTTP_404_NOT_FOUND,
                    "errors": {
                        "detail": "User not found."
                    },
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if user.id == request.user.id:

            return Response(
                {
                    "success": False,
                    "status_code": status.HTTP_400_BAD_REQUEST,
                    "errors": {
                        "detail": "Admin cannot flag their own account."
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if user.is_flagged:

            return Response(
                {
                    "success": False,
                    "status_code": status.HTTP_400_BAD_REQUEST,
                    "errors": {
                        "detail": "User is already flagged."
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.is_flagged = True
        user.save()

        AdminActionLog.objects.create(
            admin=request.user,
            action="USER_FLAGGED",
            target_user=user,
            reason="User flagged by admin.",
        )

        AuditTrail.objects.create(
            actor=request.user,
            category="ADMIN",
            action="USER_FLAGGED",
            description="Admin flagged a user.",
            target_type="User",
            target_id=str(user.id),
            metadata={
                "target_user_id": user.id,
            },
        )

        return success_response(
            message="User flagged successfully.",
            data={
                "id": user.id,
                "email": user.email,
                "role": user.role,
                "is_flagged": user.is_flagged,
            },
            status_code=status.HTTP_200_OK,
        )


@extend_schema(
    summary="Retrieve and filter user accounts.",
    description=(
        "Retrieve user accounts with optional role and verification "
        "filters, searching, and ordering. Admin access required."
    ),
)
class UserListAPIView(ListAPIView):

    permission_classes = [IsAdmin]

    serializer_class = UserListSerializer

    queryset = User.objects.order_by("id")

    filter_backends = [
        DjangoFilterBackend,
        SearchFilter,
        OrderingFilter,
    ]

    filterset_fields = ["role", "is_verified"]

    search_fields = [
        "username",
        "email",
    ]

    ordering_fields = [
        "id",
        "created_at",
        "username",
    ]


class AdminAuditLogListAPIView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
    summary="Retrieve administrative audit logs.",
    responses={200: dict},
    description=(
        "Retrieve administrator audit logs, including the admin, "
        "action, target user, target job, reason, and creation time."
    ),
    tags=["Admin Audit Logs"],
    )
    def get(self, request):

        logs = AdminActionLog.objects.select_related(
            "admin",
            "target_user",
            "target_job",
        ).order_by("-created_at")

        data = []

        for log in logs:
            data.append(
                {
                    "id": log.id,
                    "admin": log.admin.email,
                    "action": log.action,
                    "target_user": (
                        log.target_user.email
                        if log.target_user
                        else None
                    ),
                    "target_job": (
                        log.target_job.title
                        if log.target_job
                        else None
                    ),
                    "reason": log.reason,
                    "created_at": log.created_at,
                }
            )

        return success_response(
            message="Admin audit logs fetched successfully.",
            data=data,
            status_code=status.HTTP_200_OK,
        )



class AuditTrailListAPIView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
    summary="Retrieve system audit trail records.",
    responses={200: dict},
    description=(
        "Keep the original beginning of the description here, "
        "records, including actor, category, action, "
        "description, metadata, IP address, and timestamp."
    ),
    tags=["Admin Audit Logs"],
    )
    def get(self, request):
        logs = AuditTrail.objects.select_related("actor").all()[:100]

        data = []
        for log in logs:
            data.append({
                "id": log.id,
                "actor": log.actor.email if log.actor else None,
                "category": log.category,
                "action": log.action,
                "description": log.description,
                "target_type": log.target_type,
                "target_id": log.target_id,
                "metadata": log.metadata,
                "ip_address": log.ip_address,
                "created_at": log.created_at,
            })

        return Response(data)