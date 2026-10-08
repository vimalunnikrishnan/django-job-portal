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


    class Meta:
        indexes = [
            models.Index(
                fields=["status", "-applied_at"],
                name="application_status_applied_idx",
            ),
        ]


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


class AIInterview(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("SCHEDULED", "Scheduled"),
        ("IN_PROGRESS", "In Progress"),
        ("COMPLETED", "Completed"),
        ("FAILED", "Failed"),
    ]

    application = models.OneToOneField(
        Application,
        on_delete=models.CASCADE,
        related_name="ai_interview",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING",
    )

    call_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    final_score = models.FloatField(
        null=True,
        blank=True,
    )

    started_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"AI Interview - {self.application}"


class AIInterviewSession(models.Model):
    STATUS_CHOICES = [
        ("CREATED", "Created"),
        ("IN_PROGRESS", "In Progress"),
        ("COMPLETED", "Completed"),
        ("FAILED", "Failed"),
    ]

    interview = models.ForeignKey(
        AIInterview,
        on_delete=models.CASCADE,
        related_name="sessions",
    )

    session_id = models.CharField(
        max_length=255,
        unique=True,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="CREATED",
    )

    current_question_index = models.PositiveIntegerField(default=0)

    started_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    ended_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return f"Session {self.session_id} - {self.interview}"


class AIQuestion(models.Model):
    session = models.ForeignKey(
        AIInterviewSession,
        on_delete=models.CASCADE,
        related_name="questions",
    )

    question_template = models.ForeignKey(
        "QuestionTemplate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_questions",
    )
    
    question = models.TextField()

    sequence_number = models.PositiveIntegerField()

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["sequence_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["session", "sequence_number"],
                name="unique_session_question_sequence",
            ),
        ]

    def __str__(self):
        return f"Question {self.sequence_number} - {self.session}"


class AIAnswer(models.Model):
    question = models.OneToOneField(
        AIQuestion,
        on_delete=models.CASCADE,
        related_name="answer",
    )

    answer_text = models.TextField(
        blank=True,
        default="",
    )

    transcript = models.TextField(
        blank=True,
        default="",
    )

    transcript_data = models.JSONField(
        default=dict,
        blank=True,
    )

    answered_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return f"Answer - Question {self.question.sequence_number}"
    

class CallLog(models.Model):
    EVENT_CHOICES = [
        ("TRIGGERED", "Triggered"),
        ("SCHEDULED", "Scheduled"),
        ("STARTED", "Started"),
        ("COMPLETED", "Completed"),
        ("FAILED", "Failed"),
    ]

    interview = models.ForeignKey(
        AIInterview,
        on_delete=models.CASCADE,
        related_name="call_logs",
    )

    triggered_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_call_logs",
    )

    event = models.CharField(
        max_length=20,
        choices=EVENT_CHOICES,
    )

    reason = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    details = models.JSONField(
        default=dict,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    def __str__(self):
        return f"{self.interview} - {self.event}"


class AIInterviewQuestion(models.Model):
    interview = models.ForeignKey(
        AIInterview,
        on_delete=models.CASCADE,
        related_name="questions",
    )

    question = models.TextField()

    sequence_number = models.PositiveIntegerField()

    answer = models.TextField(
        blank=True,
        default="",
    )

    transcript = models.TextField(
        blank=True,
        default="",
    )

    score = models.FloatField(
        null=True,
        blank=True,
    )

    feedback = models.TextField(
        blank=True,
        default="",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sequence_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["interview", "sequence_number"],
                name="unique_interview_question_sequence",
            ),
        ]

    def __str__(self):
        return f"Question {self.sequence_number} - {self.interview}"


class QuestionTemplate(models.Model):
    CATEGORY_CHOICES = [
        ("INTRODUCTION", "Introduction"),
        ("EXPERIENCE", "Experience"),
        ("SKILLS", "Skills"),
        ("AVAILABILITY", "Availability"),
        ("SALARY", "Salary"),
    ]

    question = models.TextField()

    follow_up_question = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="parent_questions",
    )

    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
    )
    order = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.category} - {self.question}"


class JobQuestionMapping(models.Model):
    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name="question_mappings",
    )

    question_template = models.ForeignKey(
        QuestionTemplate,
        on_delete=models.CASCADE,
        related_name="job_mappings",
    )

    order = models.PositiveIntegerField(default=1)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order"]
        constraints = [
            models.UniqueConstraint(
                fields=["job", "question_template"],
                name="unique_job_question_template",
            )
        ]

    def __str__(self):
        return f"{self.job.title} - {self.question_template.question}"


class AIAnswerEvaluation(models.Model):
    answer = models.OneToOneField(
        AIAnswer,
        on_delete=models.CASCADE,
        related_name="evaluation",
    )

    relevance_score = models.FloatField(default=0)
    completeness_score = models.FloatField(default=0)
    keyword_score = models.FloatField(default=0)
    overall_score = models.FloatField(default=0)

    confidence = models.FloatField(default=0)

    ai_annotations = models.JSONField(
        default=dict,
        blank=True,
    )

    feedback = models.TextField(
        blank=True,
        default="",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class InterviewAvailability(models.Model):
    employer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="interview_availability",
        limit_choices_to={"role": "EMPLOYER"},
    )

    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name="interview_availability",
    )

    start_time = models.DateTimeField()
    end_time = models.DateTimeField()

    is_available = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start_time"]

    def __str__(self):
        return (
            f"{self.job.title} - "
            f"{self.start_time} to {self.end_time}"
        )


class InterviewSchedule(models.Model):
    STATUS_CHOICES = [
        ("SCHEDULED", "Scheduled"),
        ("CONFIRMED", "Confirmed"),
        ("RESCHEDULED", "Rescheduled"),
        ("CANCELLED", "Cancelled"),
        ("COMPLETED", "Completed"),
    ]

    interview = models.OneToOneField(
        AIInterview,
        on_delete=models.CASCADE,
        related_name="schedule",
    )

    availability = models.ForeignKey(
        InterviewAvailability,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="schedules",
    )

    scheduled_start = models.DateTimeField()
    scheduled_end = models.DateTimeField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="SCHEDULED",
    )

    confirmation_sent = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return (
            f"{self.interview} - "
            f"{self.scheduled_start}"
        )