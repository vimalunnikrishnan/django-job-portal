from django.db.models.functions import TruncDate
from django.db.models import Count
from rest_framework import status
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from django_filters.rest_framework import DjangoFilterBackend

from .models import (
    User,
    EmployerProfile,
    CandidateProfile,
    AdminActionLog,
)

from .services.resume_parser import extract_resume_text
from .services.resume_nlp import parse_resume

from .permissions import (
    IsAdmin,
    IsEmployer,
    IsCandidate,
)

from .response import success_response

from .serializers import (
    SignupSerializer,
    EmployerProfileSerializer,
    ResumeUploadSerializer,
    UserListSerializer,
)

from jobs.models import Job, Application

class SignupAPIView(APIView):

    permission_classes = [AllowAny]

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

        except Exception as e:

            return Response(
                {
                    "success": False,
                    "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "errors": {
                        "detail": "Unable to parse resume.",
                        "error": str(e),
                    },
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        parsed_resume = parse_resume(extracted_text)

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