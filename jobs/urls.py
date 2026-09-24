from django.urls import path

from .views import (
    ApplyJobAPIView,
    FeaturedJobListAPIView,
    LatestJobListAPIView,
    JobCreateAPIView,
    JobDeleteAPIView,
    JobDetailAPIView,
    JobListAPIView,
    JobUpdateAPIView,
    ApplicationStatusUpdateAPIView,
    MyApplicationsAPIView,
    EmployerApplicationsAPIView,
    EmployerAnalyticsAPIView,
    SaveJobAPIView,
    SavedJobListAPIView,
    UnsaveJobAPIView,
    AdminJobDeactivateAPIView,
    JobMatchPercentageAPIView,
    JobCandidateRankingAPIView,
    AutoProcessApplicationAPIView,
)

urlpatterns = [

    path(
        "",
        JobCreateAPIView.as_view(),
        name="job-create",
    ),

    path(
        "list/",
        JobListAPIView.as_view(),
        name="job-list",
    ),

    path(
        "<int:pk>/match/",
        JobMatchPercentageAPIView.as_view(),
        name="job-match-percentage",
    ),

    path(
        "<int:pk>/",
        JobDetailAPIView.as_view(),
        name="job-detail",
    ),

    path(
        "<int:pk>/update/",
        JobUpdateAPIView.as_view(),
        name="job-update",
    ),

    path(
        "<int:pk>/delete/",
        JobDeleteAPIView.as_view(),
        name="job-delete",
    ),

    path(
        "featured/",
        FeaturedJobListAPIView.as_view(),
        name="featured-jobs",
    ),

    path(
        "latest/",
        LatestJobListAPIView.as_view(),
        name="latest-jobs",
    ),

    path(
        "<int:pk>/apply/",
        ApplyJobAPIView.as_view(),
        name="apply-job",
    ),

    path(
        "applications/<int:pk>/status/",
        ApplicationStatusUpdateAPIView.as_view(),
        name="application-status-update",
    ),

    path(
        "applications/",
        MyApplicationsAPIView.as_view(),
        name="my-applications",
    ),

    path(
        "employer/applications/",
        EmployerApplicationsAPIView.as_view(),
        name="employer-applications",
    ),

    path(
        "employer/analytics/",
        EmployerAnalyticsAPIView.as_view(),
        name="employer-analytics",
    ),

    path(
        "my-applications/",
        MyApplicationsAPIView.as_view(),
        name="my-applications",
    ),

    path(
        "saved/",
        SavedJobListAPIView.as_view(),
        name="saved-jobs",
    ),

    path(
        "<int:pk>/save/",
        SaveJobAPIView.as_view(),
        name="save-job",
    ),

    path(
        "<int:pk>/unsave/",
        UnsaveJobAPIView.as_view(),
        name="unsave-job",
    ),

    path(
        "admin/<int:pk>/deactivate/",
        AdminJobDeactivateAPIView.as_view(),
        name="admin-job-deactivate",
    ),

    path(
        "<int:pk>/candidates/ranking/",
        JobCandidateRankingAPIView.as_view(),
        name="job-candidate-ranking",
    ),

    path(
        "applications/<int:pk>/auto-process/",
        AutoProcessApplicationAPIView.as_view(),
        name="application-auto-process",
    ),
]