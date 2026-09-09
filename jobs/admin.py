from django.contrib import admin

from .models import (
    Job,
    Application,
)


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "title",
        "employer",
        "location",
        "status",
        "is_active",
        "is_featured",
    )

    search_fields = (
        "title",
        "location",
        "employer__email",
    )

    list_filter = (
        "status",
        "job_type",
        "is_active",
        "is_featured",
    )

    ordering = (
        "-created_at",
    )


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "job",
        "candidate",
        "status",
        "applied_at",
    )

    search_fields = (
        "candidate__email",
        "job__title",
    )

    list_filter = (
        "status",
    )

    ordering = (
        "-applied_at",
    )