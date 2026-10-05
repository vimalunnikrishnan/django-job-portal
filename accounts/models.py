from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):

    email = models.EmailField(unique=True)

    phone = models.CharField(
        max_length=15,
        blank=True,
    )

    ROLE_CHOICES = [
        ("ADMIN", "Admin"),
        ("EMPLOYER", "Employer"),
        ("CANDIDATE", "Candidate"),
    ]

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
    )

    is_verified = models.BooleanField(default=False)

    is_flagged = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"

    REQUIRED_FIELDS = ["username"]

    def __str__(self):
        return self.email


class EmployerProfile(models.Model):

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="employer_profile",
    )

    company_name = models.CharField(max_length=200)

    website = models.URLField(blank=True)

    domain = models.CharField(
        max_length=150,
        default="",
    )

    company_size = models.PositiveIntegerField(default=0)

    is_company_verified = models.BooleanField(default=False)

    is_deleted = models.BooleanField(default=False)

    def __str__(self):
        return self.company_name


class CandidateProfile(models.Model):

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="candidate_profile",
    )

    skills = models.TextField()

    education = models.CharField(
        max_length=200,
        default="",
    )

    experience = models.PositiveIntegerField(default=0)

    expected_salary = models.PositiveIntegerField(default=0)

    resume = models.FileField(
        upload_to="resumes/",
        blank=True,
        null=True,
    )

    is_deleted = models.BooleanField(default=False)

    is_available_for_ai_interview = models.BooleanField(default=True)

    def __str__(self):
        return self.user.email


class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ("SHORTLISTED", "Shortlisted"),
        ("REJECTED", "Rejected"),
        ("INTERVIEW", "Interview"),
        ("GENERAL", "General"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications",
    )

    notification_type = models.CharField(
        max_length=20,
        choices=NOTIFICATION_TYPES,
    )

    title = models.CharField(max_length=200)

    message = models.TextField()

    is_read = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - {self.title}"


class EmailDeliveryLog(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("SENT", "Sent"),
        ("FAILED", "Failed"),
    ]

    recipient_email = models.EmailField()
    subject = models.CharField(max_length=200)
    template_name = models.CharField(
        max_length=100,
        blank=True,
    )
    notification_type = models.CharField(
        max_length=20,
        blank=True,
    )
    context = models.JSONField(
        default=dict,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING",
    )
    error_message = models.TextField(
        blank=True,
    )
    attempt_count = models.PositiveIntegerField(
        default=0,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"{self.recipient_email} - {self.subject} - {self.status}"


class AdminActionLog(models.Model):

    ACTION_CHOICES = [
        ("EMPLOYER_APPROVED", "Employer Approved"),
        ("USER_BLOCKED", "User Blocked"),
        ("USER_UNBLOCKED", "User Unblocked"),
        ("USER_FLAGGED", "User Flagged"),
        ("JOB_DEACTIVATED", "Job Deactivated"),
    ]

    admin = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="admin_actions",
        limit_choices_to={"role": "ADMIN"},
    )

    action = models.CharField(
        max_length=50,
        choices=ACTION_CHOICES,
    )

    target_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admin_action_targets",
    )

    target_job = models.ForeignKey(
        "jobs.Job",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admin_action_logs",
    )

    reason = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    def __str__(self):
        return f"{self.admin.email} - {self.action}"