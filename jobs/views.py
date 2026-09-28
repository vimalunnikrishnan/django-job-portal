from django.core.cache import cache
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
from accounts.services.ats_scoring import calculate_and_save_ats_score
from accounts.services.ats_ranking import rank_candidates_for_job
from accounts.services.auto_shortlisting import auto_process_application

from .filters import JobFilter
from .models import Job, Application, SavedJob, ATSScore
from .serializers import JobSerializer, ApplicationSerializer, ApplicationStatusSerializer, SavedJobSerializer, ATSScoreSerializer, RankedCandidateSerializer
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

    def list(self, request, *args, **kwargs):
        cache_key = f"job-list:{request.get_full_path()}"

        cached_data = cache.get(cache_key)

        if cached_data is not None:
            return Response(cached_data)

        response = super().list(request, *args, **kwargs)

        cache.set(
            cache_key,
            response.data,
            timeout=60,
        )

        return response


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


class AutoProcessApplicationAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        application = get_object_or_404(
            Application,
            pk=pk,
        )

        if application.status != "APPLIED":
            return Response(
        {
            "success": False,
            "status_code": status.HTTP_400_BAD_REQUEST,
            "errors": {
                "detail": (
                    "Only applications with APPLIED status "
                    "can be auto-processed."
                )
            },
        },
        status=status.HTTP_400_BAD_REQUEST,
    )

        if request.user.role != "EMPLOYER":
            return Response(
                {
                    "success": False,
                    "status_code": status.HTTP_403_FORBIDDEN,
                    "errors": {
                        "detail": "Only employers can auto-process applications."
                    },
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if application.job.employer != request.user:
            return Response(
                {
                    "success": False,
                    "status_code": status.HTTP_403_FORBIDDEN,
                    "errors": {
                        "detail": "You do not have permission to process this application."
                    },
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        previous_status = application.status

        shortlist_threshold = request.data.get(
            "shortlist_threshold",
            70,
        )

        try:
            shortlist_threshold = float(shortlist_threshold)
        except (TypeError, ValueError):
            return Response(
                {
                    "success": False,
                    "status_code": status.HTTP_400_BAD_REQUEST,
                    "errors": {
                        "shortlist_threshold": (
                            "Shortlist threshold must be a valid number."
                        )
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = auto_process_application(
            application,
            shortlist_threshold=shortlist_threshold,
        )

        return success_response(
            message="Application processed successfully.",
            data={
                "application_id": result["application"].id,
                "candidate_email": result["application"].candidate.email,
                "previous_status": previous_status,
                "new_status": result["application"].status,
                "match_percentage": result["ats_score"].match_percentage,
                "shortlist_threshold": shortlist_threshold,
                "action": result["eligibility"]["action"],
                "reason": result["eligibility"]["reason"],
            },
            status_code=status.HTTP_200_OK,
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


class JobMatchPercentageAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):

        job = get_object_or_404(
            Job,
            pk=pk,
            is_active=True,
        )

        try:

            candidate = CandidateProfile.objects.get(
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

        ats_score = calculate_and_save_ats_score(
            job,
            candidate,
        )

        serializer = ATSScoreSerializer(
            ats_score,
        )

        return success_response(
            message="Job match percentage calculated successfully.",
            data=serializer.data,
            status_code=status.HTTP_200_OK,
        )


class JobCandidateRankingAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        job = get_object_or_404(
            Job,
            pk=pk,
            is_active=True,
        )

        if request.user.role != "EMPLOYER":
            return Response(
                {
                    "success": False,
                    "status_code": status.HTTP_403_FORBIDDEN,
                    "errors": {
                        "detail": "Only employers can view candidate rankings."
                    },
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if job.employer != request.user:
            return Response(
                {
                    "success": False,
                    "status_code": status.HTTP_403_FORBIDDEN,
                    "errors": {
                        "detail": "You do not have permission to view this job's candidates."
                    },
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        ranked_candidates = rank_candidates_for_job(job)

        data = []

        for rank, item in enumerate(ranked_candidates, start=1):
            candidate = item["candidate"]
            application = item["application"]
            ats_score = item["ats_score"]

            data.append(
                {
                    "rank": rank,
                    "candidate_id": candidate.id,
                    "candidate_email": candidate.user.email,
                    "application_id": application.id,
                    "application_status": application.status,
                    "skill_score": ats_score.skill_score,
                    "experience_score": ats_score.experience_score,
                    "education_score": ats_score.education_score,
                    "match_percentage": ats_score.match_percentage,
                }
            )

        serializer = RankedCandidateSerializer(
            data,
            many=True,
        )

        return success_response(
            message="Candidate ranking retrieved successfully.",
            data=serializer.data,
            status_code=status.HTTP_200_OK,
        )