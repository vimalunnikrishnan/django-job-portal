from django.urls import path

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from .views import (
    SignupAPIView,
    ProfileAPIView,
    UserListAPIView,
    EmployerDashboardAPIView,
    EmployerProfileAPIView,
    CandidateDashboardAPIView,
    ResumeUploadAPIView,
    AdminDashboardAPIView,
    EmployerApprovalAPIView,
    UserBlockAPIView,
    UserUnblockAPIView,
    AdminUserGrowthAPIView,
    AdminJobActivityAPIView,
    AdminUserFlagAPIView,
    AdminAuditLogListAPIView,
)

urlpatterns = [

    # Authentication APIs
    path("signup/", SignupAPIView.as_view(), name="signup"),
    path("login/", TokenObtainPairView.as_view(), name="login"),
    path("refresh/", TokenRefreshView.as_view(), name="refresh"),

    # User Profile
    path("profile/", ProfileAPIView.as_view(), name="profile"),

    # Admin APIs
    path("users/", UserListAPIView.as_view(), name="users"),
    path(
        "admin-dashboard/",
        AdminDashboardAPIView.as_view(),
        name="admin-dashboard",
    ),

    # Employer APIs
    path(
        "employer/",
        EmployerDashboardAPIView.as_view(),
        name="employer",
    ),
    path(
        "employer/profile/",
        EmployerProfileAPIView.as_view(),
        name="employer-profile",
    ),

    # Candidate APIs
    path(
        "candidate/",
        CandidateDashboardAPIView.as_view(),
        name="candidate",
    ),
    path(
        "upload-resume/",
        ResumeUploadAPIView.as_view(),
        name="upload-resume",
    ),

    path(
        "admin/employers/<int:user_id>/approve/",
        EmployerApprovalAPIView.as_view(),
        name="admin-employer-approve",
    ),

    path(
        "admin/users/<int:user_id>/block/",
        UserBlockAPIView.as_view(),
        name="admin-user-block",
    ),
    path(
        "admin/users/<int:user_id>/unblock/",
        UserUnblockAPIView.as_view(),
        name="admin-user-unblock",
    ),

    path(
        "admin/user-growth/",
        AdminUserGrowthAPIView.as_view(),
        name="admin-user-growth",
    ),

    path(
        "admin/job-activity/",
        AdminJobActivityAPIView.as_view(),
        name="admin-job-activity",
    ),

    path(
        "admin/users/<int:user_id>/flag/",
        AdminUserFlagAPIView.as_view(),
        name="admin-user-flag",
    ),

    path(
        "admin/audit-logs/",
        AdminAuditLogListAPIView.as_view(),
        name="admin-audit-logs",
    ),
]