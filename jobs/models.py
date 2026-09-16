from django.db import models
from accounts.models import User


class Job(models.Model):

    JOB_TYPE_CHOICES = [
        ("FULL_TIME", "Full Time"),
        ("PART_TIME", "Part Time"),
        ("INTERNSHIP", "Internship"),
        ("CONTRACT", "Contract"),
        ("REMOTE", "Remote"),
    ]

    STATUS_CHOICES = [
        ("OPEN", "Open"),
        ("CLOSED", "Closed"),
    ]

    employer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="jobs",
        limit_choices_to={"role": "EMPLOYER"},
    )

    title = models.CharField(max_length=200)

    description = models.TextField()

    skills = models.TextField(
        blank=True,
        help_text="Comma separated skills",
    )

    experience = models.PositiveIntegerField(
        default=0,
        help_text="Required experience (years)",
    )

    min_salary = models.PositiveIntegerField(default=0)

    max_salary = models.PositiveIntegerField(default=0)

    location = models.CharField(max_length=200)

    job_type = models.CharField(
        max_length=20,
        choices=JOB_TYPE_CHOICES,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="OPEN",
    )

    is_active = models.BooleanField(default=True)
    moderation_reason = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    is_featured = models.BooleanField(default=False)

    def __str__(self):
        return self.title


class Application(models.Model):

    STATUS_CHOICES = [
        ("APPLIED", "Applied"),
        ("SHORTLISTED", "Shortlisted"),
        ("INTERVIEW", "Interview Scheduled"),
        ("REJECTED", "Rejected"),
        ("SELECTED", "Selected"),
    ]

    candidate = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="applications",
        limit_choices_to={"role": "CANDIDATE"},
    )

    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name="applications",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="APPLIED",
    )

    applied_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.candidate.email} - {self.job.title}"


class SavedJob(models.Model):

    candidate = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="saved_jobs",
        limit_choices_to={"role": "CANDIDATE"},
    )

    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name="saved_by",
    )

    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["candidate", "job"],
                name="unique_saved_job",
            )
        ]

    def __str__(self):
        return f"{self.candidate.email} - {self.job.title}"


class ATSScore(models.Model):

    candidate = models.ForeignKey(
        "accounts.CandidateProfile",
        on_delete=models.CASCADE,
        related_name="ats_scores",
    )

    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name="ats_scores",
    )

    skill_score = models.FloatField(default=0)

    experience_score = models.FloatField(default=0)

    education_score = models.FloatField(default=0)

    match_percentage = models.FloatField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("candidate", "job")

    def __str__(self):
        return (
            f"{self.candidate.user.email} - "
            f"{self.job.title} - "
            f"{self.match_percentage}%"
        )