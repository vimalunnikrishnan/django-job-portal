from django.contrib import admin
from .models import User, EmployerProfile, CandidateProfile


@admin.register(User)
class UserAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "email",
        "username",
        "role",
        "is_verified",
    )

    search_fields = (
        "email",
        "username",
    )

    list_filter = (
        "role",
        "is_verified",
    )


@admin.register(EmployerProfile)
class EmployerProfileAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "company_name",
        "user",
        "domain",
        "company_size",
        "is_company_verified",
        "is_deleted",
    )

    search_fields = (
        "company_name",
        "domain",
    )


@admin.register(CandidateProfile)
class CandidateProfileAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "user",
        "education",
        "experience",
        "expected_salary",
        "is_deleted",
    )

    search_fields = (
        "user__email",
        "education",
    )

