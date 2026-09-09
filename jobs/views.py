from django.db.models import Q
from django.shortcuts import get_object_or_404

from django_filters.rest_framework import DjangoFilterBackend

from rest_framework import status
from rest_framework.filters import (
    OrderingFilter,
    SearchFilter,
)
from rest_framework.generics import (
    ListAPIView,
    RetrieveAPIView,
    UpdateAPIView,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import AdminActionLog, CandidateProfile
from accounts.permissions import IsEmployer, IsCandidate, IsAdmin
from accounts.response import success_response

from .filters import JobFilter
from .models import Job, Application, SavedJob
from .serializers import JobSerializer, ApplicationSerializer, ApplicationStatusSerializer, SavedJobSerializer
from .constants.application_constants import (
    APPLICATION_STATUS_TRANSITIONS,
)

class JobCreateAPIView(APIView):

    permission_classes = [IsEmployer]

    def post(self, request):

        serializer = JobSerializer(data=request.data)

        if serializer.is_valid():

            serializer.save(
                employer=request.user,
            )

            return success_response(
                message="Job created successfully.",
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


class JobListAPIView(ListAPIView):

    permission_classes = [IsAuthenticated]

    serializer_class = JobSerializer

    queryset = Job.objects.select_related(
        "employer"
    ).filter(
        is_active=True,
    ).order_by(
        "-created_at"
    )

    filter_backends = [
        DjangoFilterBackend,
        SearchFilter,
        OrderingFilter,
    ]

    filterset_class = JobFilter

    search_fields = [
        "title",
        "description",
        "skills",
        "location",
    ]

    ordering_fields = [
        "created_at",
        "min_salary",
        "max_salary",
        "experience",
    ]


class JobDetailAPIView(RetrieveAPIView):

    permission_classes = [IsAuthenticated]

    serializer_class = JobSerializer

    queryset = Job.objects.select_related(
        "employer"
    ).filter(
        is_active=True,
    )


class JobUpdateAPIView(UpdateAPIView):

    permission_classes = [IsEmployer]

    serializer_class = JobSerializer

    def get_queryset(self):

        return Job.objects.select_related(
            "employer"
        ).filter(
            employer=self.request.user,
            is_active=True,
        )


class JobDeleteAPIView(APIView):

    permission_classes = [IsEmployer]

    def delete(self, request, pk):

        job = get_object_or_404(
            Job,
            pk=pk,
            employer=request.user,
            is_active=True,
        )

        job.is_active = False
        job.save()

        return success_response(
            message="Job deleted successfully.",
            status_code=status.HTTP_200_OK,
        )


class FeaturedJobListAPIView(ListAPIView):

    permission_classes = [IsAuthenticated]

    serializer_class = JobSerializer

    queryset = Job.objects.select_related(
        "employer"
    ).filter(
        is_active=True,
        is_featured=True,
    ).order_by(
        "-created_at"
    )


class LatestJobListAPIView(ListAPIView):

    permission_classes = [IsAuthenticated]

    serializer_class = JobSerializer

    queryset = Job.objects.select_related(
        "employer"
    ).filter(
        is_active=True,
    ).order_by(
        "-created_at"
    )[:10]


class ApplyJobAPIView(APIView):

    permission_classes = [IsCandidate]

    def post(self, request, pk):

        job = get_object_or_404(
            Job,
            pk=pk,
            is_active=True,
            status="OPEN",
        )

        if Application.objects.filter(
            job=job,
            candidate=request.user,
        ).exists():

            return Response(
                {
                    "success": False,
                    "status_code": status.HTTP_400_BAD_REQUEST,
                    "errors": {
                        "detail": "You have already applied for this job."
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:

            profile = CandidateProfile.objects.get(
                user=request.user,
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

        if not profile.resume:

            return Response(
                {
                    "success": False,
                    "status_code": status.HTTP_400_BAD_REQUEST,
                    "errors": {
                        "detail": "Please upload your resume before applying."
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        application = Application.objects.create(
            job=job,
            candidate=request.user,
        )

        serializer = ApplicationSerializer(
            application,
        )

        return success_response(
            message="Job application submitted successfully.",
            data=serializer.data,
            status_code=status.HTTP_201_CREATED,
        )
    

class MyApplicationsAPIView(ListAPIView):

    permission_classes = [IsCandidate]

    serializer_class = ApplicationSerializer

    def get_queryset(self):

        return Application.objects.select_related(
            "job",
            "candidate",
        ).filter(
            candidate=self.request.user,
        ).order_by(
            "-applied_at"
        )


class MyApplicationsAPIView(ListAPIView):

    permission_classes = [IsCandidate]

    serializer_class = ApplicationSerializer

    def get_queryset(self):

        return Application.objects.select_related(
            "job",
            "candidate",
        ).filter(
            candidate=self.request.user,
        ).order_by(
            "-applied_at"
        )

        
class EmployerApplicationsAPIView(ListAPIView):

    permission_classes = [IsEmployer]

    serializer_class = ApplicationSerializer

    def get_queryset(self):

        queryset = Application.objects.select_related(
            "job",
            "candidate",
        ).filter(
            job__employer=self.request.user,
        )

        status_filter = self.request.query_params.get("status")

        if status_filter:
            queryset = queryset.filter(
                status=status_filter.upper()
            )

        search = self.request.query_params.get("search")

        if search:
            queryset = queryset.filter(
                Q(candidate__email__icontains=search)
                | Q(candidate__username__icontains=search)
                | Q(job__title__icontains=search)
            )

        return queryset.order_by(
            "-applied_at"
        )


class EmployerAnalyticsAPIView(APIView):

    permission_classes = [IsEmployer]

    def get(self, request):

        employer = request.user

        total_jobs = Job.objects.filter(
            employer=employer,
        ).count()

        active_jobs = Job.objects.filter(
            employer=employer,
            is_active=True,
        ).count()

        closed_jobs = Job.objects.filter(
            employer=employer,
            status="CLOSED",
        ).count()

        applications = Application.objects.filter(
            job__employer=employer,
        )

        total_applications = applications.count()

        applied = applications.filter(
            status="APPLIED",
        ).count()

        shortlisted = applications.filter(
            status="SHORTLISTED",
        ).count()

        interview = applications.filter(
            status="INTERVIEW",
        ).count()

        selected = applications.filter(
            status="SELECTED",
        ).count()

        rejected = applications.filter(
            status="REJECTED",
        ).count()

        shortlist_ratio = 0

        if total_applications > 0:
            shortlist_ratio = round(
                (shortlisted / total_applications) * 100,
                2,
            )

        return success_response(
            message="Employer analytics fetched successfully.",
            data={
                "total_jobs": total_jobs,
                "active_jobs": active_jobs,
                "closed_jobs": closed_jobs,
                "total_applications": total_applications,
                "applied": applied,
                "shortlisted": shortlisted,
                "interview": interview,
                "selected": selected,
                "rejected": rejected,
                "shortlist_ratio": shortlist_ratio,
            },
            status_code=status.HTTP_200_OK,
        )

        
class ApplicationStatusUpdateAPIView(APIView):

    permission_classes = [IsEmployer]


    def patch(self, request, pk):

        application = get_object_or_404(
            Application,
            pk=pk,
        )

        if application.job.employer != request.user:

            return Response(
                {
                    "success": False,
                    "status_code": status.HTTP_403_FORBIDDEN,
                    "errors": {
                        "detail": "Permission denied."
                    },
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ApplicationStatusSerializer(
            application,
            data=request.data,
            partial=True,
        )

        if serializer.is_valid():

            new_status = serializer.validated_data["status"]

            current_status = application.status

            if new_status not in APPLICATION_STATUS_TRANSITIONS[current_status]:

                return Response(
                    {
                        "success": False,
                        "status_code": status.HTTP_400_BAD_REQUEST,
                        "errors": {
                            "detail": f"Cannot move from {current_status} to {new_status}."
                        },
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            serializer.save()

            return success_response(
                message="Application status updated successfully.",
                data=serializer.data,
                status_code=status.HTTP_200_OK,
            )

        return Response(
            {
                "success": False,
                "status_code": status.HTTP_400_BAD_REQUEST,
                "errors": serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )


class SaveJobAPIView(APIView):

    permission_classes = [IsCandidate]

    def post(self, request, pk):

        job = get_object_or_404(
            Job,
            pk=pk,
            is_active=True,
        )

        if SavedJob.objects.filter(
            candidate=request.user,
            job=job,
        ).exists():

            return Response(
                {
                    "success": False,
                    "status_code": status.HTTP_400_BAD_REQUEST,
                    "errors": {
                        "detail": "Job is already saved."
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        saved_job = SavedJob.objects.create(
            candidate=request.user,
            job=job,
        )

        return success_response(
            message="Job saved successfully.",
            data={
                "id": saved_job.id,
                "job": job.id,
                "title": job.title,
                "saved_at": saved_job.saved_at,
            },
            status_code=status.HTTP_201_CREATED,
        )


class SavedJobListAPIView(ListAPIView):

    permission_classes = [IsCandidate]

    serializer_class = ApplicationSerializer

    def get_queryset(self):
        return SavedJob.objects.select_related(
            "job",
        ).filter(
            candidate=self.request.user,
        ).order_by(
            "-saved_at"
        )


class SavedJobListAPIView(ListAPIView):

    permission_classes = [IsCandidate]

    serializer_class = SavedJobSerializer

    def get_queryset(self):
        return SavedJob.objects.select_related(
            "job",
        ).filter(
            candidate=self.request.user,
        ).order_by(
            "-saved_at"
        )


class UnsaveJobAPIView(APIView):

    permission_classes = [IsCandidate]

    def delete(self, request, pk):

        saved_job = get_object_or_404(
            SavedJob,
            job_id=pk,
            candidate=request.user,
        )

        saved_job.delete()

        return success_response(
            message="Job removed from saved jobs successfully.",
            status_code=status.HTTP_200_OK,
        )


class AdminJobDeactivateAPIView(APIView):

    permission_classes = [IsAdmin]

    def patch(self, request, pk):

        job = get_object_or_404(
            Job.objects.select_related("employer"),
            pk=pk,
        )

        if not job.is_active:

            return Response(
                {
                    "success": False,
                    "status_code": status.HTTP_400_BAD_REQUEST,
                    "errors": {
                        "detail": "Job is already deactivated."
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        reason = request.data.get("moderation_reason", "").strip()

        if not reason:

            return Response(
                {
                    "success": False,
                    "status_code": status.HTTP_400_BAD_REQUEST,
                    "errors": {
                        "moderation_reason": "Moderation reason is required."
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        job.is_active = False
        job.moderation_reason = reason
        job.save()

        AdminActionLog.objects.create(
            admin=request.user,
            action="JOB_DEACTIVATED",
            target_job=job,
            reason=reason,
        )

        return success_response(
            message="Job removed by admin successfully.",
            data={
                "id": job.id,
                "title": job.title,
                "employer": job.employer.email,
                "is_active": job.is_active,
                "moderation_reason": job.moderation_reason,
            },
            status_code=status.HTTP_200_OK,
        )