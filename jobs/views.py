from datetime import datetime, timedelta
from django.db.migrations import serializer
from django.utils import timezone
from django.core.cache import cache
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404

from django_filters.rest_framework import DjangoFilterBackend

import logging

logger = logging.getLogger("jobs")
ai_logger = logging.getLogger("ai_events")

from requests import request
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

from billing.services import get_active_subscription
from billing.services import can_create_job
from accounts.models import AdminActionLog, CandidateProfile
from accounts.permissions import IsEmployer, IsCandidate, IsAdmin
from accounts.response import success_response
from accounts.services.ats_scoring import calculate_and_save_ats_score
from accounts.services.ats_ranking import rank_candidates_for_job
from accounts.services.auto_shortlisting import auto_process_application
from jobs.services.ai_interview_service import create_ai_interview
from jobs.services.ai_answer_evaluation.scoring import AnswerScoringEngine
from jobs.services.ai_interview_scheduler.scheduler import AIInterviewScheduler
from jobs.services.reports.candidate_report_service import CandidateReportService
from jobs.tasks import start_ai_interview_task

from .filters import JobFilter
from .models import Job, Application, SavedJob, ATSScore, AIInterview, AIQuestion, AIAnswerEvaluation, InterviewAvailability, InterviewSchedule, InterviewReminder
from .serializers import JobSerializer, ApplicationSerializer, ApplicationStatusSerializer, SavedJobSerializer, ATSScoreSerializer, RankedCandidateSerializer, AIAnswerEvaluationSerializer, InterviewAvailabilitySerializer, InterviewScheduleSerializer
from .constants.application_constants import (
    APPLICATION_STATUS_TRANSITIONS,
)

class JobCreateAPIView(APIView):

    permission_classes = [IsEmployer]

    
    def post(self, request):
        allowed, message = can_create_job(request.user)

        if not allowed:
            return Response(
                {
                    "success": False,
                    "status_code": status.HTTP_403_FORBIDDEN,
                    "errors": {"subscription": [message]},
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = JobSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save(employer=request.user)

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
    

class InterviewAvailabilityAPIView(APIView):
    permission_classes = [IsEmployer]

    def post(self, request):
        serializer = InterviewAvailabilitySerializer(data=request.data)

        if serializer.is_valid():
            job = get_object_or_404(
                Job,
                pk=serializer.validated_data["job"].id,
                employer=request.user,
                is_active=True,
            )

            slot = serializer.save(
                employer=request.user,
            )

            return success_response(
                message="Interview availability slot created successfully.",
                data=InterviewAvailabilitySerializer(slot).data,
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


class InterviewScheduleAPIView(APIView):
    permission_classes = [IsEmployer]

    def post(self, request):
        interview_id = request.data.get("interview_id")
        availability_id = request.data.get("availability_id")

        if not interview_id or not availability_id:
            return Response(
                {
                    "success": False,
                    "status_code": status.HTTP_400_BAD_REQUEST,
                    "errors": {
                        "detail": (
                            "interview_id and availability_id are required."
                        )
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        interview = get_object_or_404(
            AIInterview.objects.select_related(
                "application__job",
            ),
            pk=interview_id,
        )

        if interview.application.job.employer != request.user:
            return Response(
                {
                    "success": False,
                    "status_code": status.HTTP_403_FORBIDDEN,
                    "errors": {
                        "detail": "You do not have permission to schedule this interview."
                    },
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        availability = get_object_or_404(
            InterviewAvailability,
            pk=availability_id,
            job=interview.application.job,
        )

        scheduler = AIInterviewScheduler()

        result = scheduler.schedule_interview(
            interview,
            availability,
        )

        if not result["success"]:
            return Response(
                {
                    "success": False,
                    "status_code": status.HTTP_400_BAD_REQUEST,
                    "errors": {
                        "detail": result["error"],
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return success_response(
            message="Interview scheduled successfully.",
            data=InterviewScheduleSerializer(
                result["schedule"]
            ).data,
            status_code=status.HTTP_201_CREATED,
        )


class InterviewRescheduleAPIView(APIView):
    permission_classes = [IsEmployer]

    def post(self, request):
        schedule_id = request.data.get("schedule_id")
        availability_id = request.data.get("availability_id")

        if not schedule_id or not availability_id:
            return Response(
                {
                    "success": False,
                    "status_code": status.HTTP_400_BAD_REQUEST,
                    "errors": {
                        "detail": (
                            "schedule_id and availability_id are required."
                        )
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        schedule = get_object_or_404(
            InterviewSchedule.objects.select_related(
                "interview__application__job",
                "availability",
            ),
            pk=schedule_id,
        )

        if schedule.interview.application.job.employer != request.user:
            return Response(
                {
                    "success": False,
                    "status_code": status.HTTP_403_FORBIDDEN,
                    "errors": {
                        "detail": (
                            "You do not have permission to reschedule "
                            "this interview."
                        )
                    },
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        new_slot = get_object_or_404(
            InterviewAvailability,
            pk=availability_id,
            job=schedule.interview.application.job,
        )

        scheduler = AIInterviewScheduler()

        result = scheduler.reschedule_interview(
            schedule,
            new_slot,
        )

        if not result["success"]:
            return Response(
                {
                    "success": False,
                    "status_code": status.HTTP_400_BAD_REQUEST,
                    "errors": {
                        "detail": result["error"],
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return success_response(
            message="Interview rescheduled successfully.",
            data=InterviewScheduleSerializer(
                result["schedule"]
            ).data,
            status_code=status.HTTP_200_OK,
        )


class AIInterviewAPIView(APIView):

    permission_classes = [IsCandidate]

    def post(self, request, pk):

        application = get_object_or_404(
            Application.objects.select_related("job", "candidate"),
            pk=pk,
            candidate=request.user,
        )

        if application.status != "SHORTLISTED":
            return Response(
                {
                    "success": False,
                    "status_code": status.HTTP_400_BAD_REQUEST,
                    "errors": {
                        "detail": (
                            "AI interview is available only for "
                            "shortlisted applications."
                        )
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        interview, created = create_ai_interview(application)

        if not created:
            return Response(
                {
                    "success": True,
                    "status_code": status.HTTP_200_OK,
                    "message": "AI interview already exists.",
                    "data": {
                        "interview_id": interview.id,
                        "status": interview.status,
                    },
                },
                status=status.HTTP_200_OK,
            )

        try:
            start_ai_interview_task.delay(interview.id)
        except Exception:
            logger.exception(
                "Failed to dispatch AI interview task for interview_id=%s",
                interview.id,
            )
            interview.status = "FAILED"
            interview.save(update_fields=["status", "updated_at"])

            return Response(
                {
                    "success": False,
                    "status_code": status.HTTP_503_SERVICE_UNAVAILABLE,
                    "errors": {
                        "detail": (
                            "AI interview service is temporarily unavailable. "
                            "Please try again later."
                        )
                    },
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {
                "success": True,
                "status_code": status.HTTP_202_ACCEPTED,
                "message": "AI interview processing started.",
                "data": {
                    "interview_id": interview.id,
                    "status": interview.status,
                },
            },
            status=status.HTTP_202_ACCEPTED,
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

        subscription = get_active_subscription(employer)

        if (
            subscription is None
            or not subscription.plan.includes_analytics
        ):
            return Response(
                {
                    "success": False,
                    "status_code": status.HTTP_403_FORBIDDEN,
                    "errors": {
                        "subscription": [
                            "Premium analytics requires an active Enterprise subscription."
                        ]
                    },
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        cache_key = f"employer-analytics:{employer.id}"

        cached_data = cache.get(cache_key)

        if cached_data is not None:
            return success_response(
                message="Employer analytics fetched successfully.",
                data=cached_data,
                status_code=status.HTTP_200_OK,
            )

        # Keep the remainder of your existing analytics method below.

        jobs = Job.objects.filter(
            employer=employer,
        )

        applications = Application.objects.filter(
            job__employer=employer,
        )

        total_jobs = jobs.count()

        active_jobs = jobs.filter(
            is_active=True,
        ).count()

        closed_jobs = jobs.filter(
            status="CLOSED",
        ).count()

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

        def conversion_ratio(numerator, denominator):
            if denominator == 0:
                return 0

            return round(
                (numerator / denominator) * 100,
                2,
            )

        shortlist_ratio = conversion_ratio(
            shortlisted,
            total_applications,
        )

        interview_ratio = conversion_ratio(
            interview,
            shortlisted,
        )

        selection_ratio = conversion_ratio(
            selected,
            interview,
        )

        job_performance = list(
            jobs.order_by("id").annotate(
                total_applications=Count("applications"),
                shortlisted=Count(
                    "applications",
                    filter=Q(
                        applications__status="SHORTLISTED",
                    ),
                ),
                interview=Count(
                    "applications",
                    filter=Q(
                        applications__status="INTERVIEW",
                    ),
                ),
                selected=Count(
                    "applications",
                    filter=Q(
                        applications__status="SELECTED",
                    ),
                ),
                rejected=Count(
                    "applications",
                    filter=Q(
                        applications__status="REJECTED",
                    ),
                ),
            ).values(
                "id",
                "title",
                "job_type",
                "status",
                "total_applications",
                "shortlisted",
                "interview",
                "selected",
                "rejected",
            )
        )

        job_performance = [
            {
                "job_id": job["id"],
                "job_title": job["title"],
                "job_type": job["job_type"],
                "status": job["status"],
                "total_applications": job["total_applications"],
                "shortlisted": job["shortlisted"],
                "interview": job["interview"],
                "selected": job["selected"],
                "rejected": job["rejected"],
            }
            for job in job_performance
        ]

        today = timezone.localdate()
        start_date = today - timedelta(days=6)

        daily_counts = applications.filter(
            applied_at__date__gte=start_date,
            applied_at__date__lte=today,
        ).annotate(
            application_date=TruncDate("applied_at"),
        ).values(
            "application_date",
        ).annotate(
            total=Count("id"),
        ).order_by(
            "application_date",
        )

        counts_by_date = {
            item["application_date"]: item["total"]
            for item in daily_counts
        }

        daily_applications = [
            {
                "date": (
                    start_date + timedelta(days=day_offset)
                ).isoformat(),
                "applications": counts_by_date.get(
                    start_date + timedelta(days=day_offset),
                    0,
                ),
            }
            for day_offset in range(7)
        ]

        data = {
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
            "funnel": {
                "applied": applied,
                "shortlisted": shortlisted,
                "interviewed": interview,
                "selected": selected,
            },
            "conversion_ratios": {
                "application_to_shortlist": shortlist_ratio,
                "shortlist_to_interview": interview_ratio,
                "interview_to_selection": selection_ratio,
            },
            "job_performance": job_performance,
            "daily_applications": daily_applications,
        }

        cache.set(
            cache_key,
            data,
            timeout=60,
        )

        return success_response(
            message="Employer analytics fetched successfully.",
            data=data,
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

            cache.delete(
                f"employer-analytics:{application.job.employer_id}"
            )

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


class AIAnswerEvaluationAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, question_id):
        question = get_object_or_404(
            AIQuestion,
            id=question_id,
        )

        answer_text = request.data.get("answer_text", "").strip()

        if not answer_text:
            return Response(
                {
                    "error": "answer_text is required."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        answer = getattr(question, "answer", None)

        if answer is None:
            from .models import AIAnswer

            answer = AIAnswer.objects.create(
                question=question,
                answer_text=answer_text,
            )
        else:
            answer.answer_text = answer_text
            answer.save(update_fields=["answer_text", "updated_at"])

        job = (
            question.session.interview.application.job
        )

        expected_keywords = []

        if job.skills:
            expected_keywords = [
                skill.strip()
                for skill in job.skills.split(",")
                if skill.strip()
            ]

        engine = AnswerScoringEngine()

        result = engine.evaluate(
            question=question.question,
            answer=answer_text,
            expected_keywords=expected_keywords,
        )

        evaluation, _ = AIAnswerEvaluation.objects.update_or_create(
            answer=answer,
            defaults={
                "relevance_score": result["relevance_score"],
                "completeness_score": result["completeness_score"],
                "keyword_score": result["keyword_score"],
                "overall_score": result["overall_score"],
                "confidence": result["confidence"],
                "ai_annotations": result["ai_annotations"],
            },
        )

        return Response(
            AIAnswerEvaluationSerializer(evaluation).data,
            status=status.HTTP_200_OK,
        )


class AIAnswerScoreAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, question_id):
        question = get_object_or_404(
            AIQuestion,
            id=question_id,
        )

        answer = getattr(question, "answer", None)

        if answer is None:
            return Response(
                {
                    "error": "No answer found for this question."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        evaluation = getattr(answer, "evaluation", None)

        if evaluation is None:
            return Response(
                {
                    "error": "Answer has not been evaluated yet."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            AIAnswerEvaluationSerializer(evaluation).data,
            status=status.HTTP_200_OK,
        )



class CandidateReportAPIView(APIView):
    permission_classes = [IsEmployer]

    def get(self, request, application_id):
        report = CandidateReportService.generate_report(
            application_id=application_id,
            employer=request.user,
        )

        if report is None:
            return Response(
                {
                    "success": False,
                    "message": "Application not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "success": True,
                "message": "Candidate report generated successfully.",
                "data": report,
            },
            status=status.HTTP_200_OK,
        )


class InterviewReminderListAPIView(APIView):
    permission_classes = [IsEmployer]

    def get(self, request):
        reminders = InterviewReminder.objects.filter(
            schedule__interview__application__job__employer=request.user,
        ).select_related(
            "schedule",
            "schedule__interview",
            "schedule__interview__application",
            "schedule__interview__application__job",
        ).order_by("-created_at")

        data = [
            {
                "id": reminder.id,
                "schedule_id": reminder.schedule_id,
                "job_title": (
                    reminder.schedule.interview.application.job.title
                ),
                "stage": reminder.stage,
                "status": reminder.status,
                "attempt_count": reminder.attempt_count,
                "error_message": reminder.error_message,
                "sent_at": reminder.sent_at,
                "created_at": reminder.created_at,
            }
            for reminder in reminders
        ]

        return success_response(
            message="Interview reminder records retrieved successfully.",
            data=data,
            status_code=status.HTTP_200_OK,
        )