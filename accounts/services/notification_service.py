from accounts.models import Notification


def create_application_notification(
    application,
    notification_type,
):
    candidate = application.candidate
    job = application.job

    if notification_type == "SHORTLISTED":
        title = "Application Shortlisted"
        message = (
            f"Your application for {job.title} has been shortlisted."
        )

    elif notification_type == "REJECTED":
        title = "Application Update"
        message = (
            f"Your application for {job.title} has been rejected."
        )

    elif notification_type == "INTERVIEW":
        title = "Interview Scheduled"
        message = (
            f"An interview has been scheduled for your application "
            f"for {job.title}."
        )

    else:
        title = "Application Update"
        message = (
            f"Your application for {job.title} has been updated."
        )

    existing_notification = Notification.objects.filter(
        user=candidate,
        notification_type=notification_type,
        title=title,
        message=message,
        is_read=False,
    ).first()

    if existing_notification:
        return existing_notification

    notification = Notification.objects.create(
        user=candidate,
        notification_type=notification_type,
        title=title,
        message=message,
    )

    return notification