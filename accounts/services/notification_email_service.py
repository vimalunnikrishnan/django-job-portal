from accounts.services.email_service import send_notification_email


def send_application_submitted_email(application):
    candidate = application.candidate
    job = application.job

    return send_notification_email(
        recipient_email=candidate.email,
        subject="Application Submitted",
        template_name="application_submitted",
        context={
            "candidate_name": candidate.get_full_name() or candidate.username,
            "job_title": job.title,
            "job_location": job.location,
        },
        notification_type="SUBMITTED",
    )


def send_application_shortlisted_email(application):
    candidate = application.candidate
    job = application.job

    return send_notification_email(
        recipient_email=candidate.email,
        subject="Application Shortlisted",
        template_name="application_shortlisted",
        context={
            "candidate_name": candidate.get_full_name() or candidate.username,
            "job_title": job.title,
        },
        notification_type="SHORTLISTED",
    )


def send_application_rejected_email(application):
    candidate = application.candidate
    job = application.job

    return send_notification_email(
        recipient_email=candidate.email,
        subject="Application Update",
        template_name="application_rejected",
        context={
            "candidate_name": candidate.get_full_name() or candidate.username,
            "job_title": job.title,
        },
        notification_type="REJECTED",
    )


def send_interview_scheduled_email(schedule):
    interview = schedule.interview
    application = interview.application
    candidate = application.candidate
    job = application.job

    return send_notification_email(
        recipient_email=candidate.email,
        subject="Interview Scheduled",
        template_name="interview_scheduled",
        context={
            "candidate_name": candidate.get_full_name() or candidate.username,
            "job_title": job.title,
            "scheduled_start": schedule.scheduled_start.isoformat(),
            "scheduled_end": schedule.scheduled_end.isoformat(),
        },
        notification_type="INTERVIEW",
    )