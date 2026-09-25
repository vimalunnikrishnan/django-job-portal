from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone

from accounts.models import EmailDeliveryLog
from accounts.services.email_template_service import (
    render_email_template,
)


def send_notification_email(
    recipient_email,
    subject,
    template_name,
    context,
    notification_type="GENERAL",
    delivery_log=None,
):
    message = render_email_template(
        template_name,
        context,
    )

    if delivery_log is None:
        delivery_log = EmailDeliveryLog.objects.create(
            recipient_email=recipient_email,
            subject=subject,
            template_name=template_name,
            notification_type=notification_type,
            context=context,
            status="PENDING",
            attempt_count=0,
        )

    try:
        delivery_log.attempt_count += 1
        delivery_log.save(
            update_fields=[
                "attempt_count",
                "context",
            ],
        )

        result = send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            fail_silently=False,
        )

        if result:
            delivery_log.status = "SENT"
            delivery_log.error_message = ""
            delivery_log.sent_at = timezone.now()
            delivery_log.save(
                update_fields=[
                    "status",
                    "error_message",
                    "sent_at",
                ],
            )
        else:
            delivery_log.status = "FAILED"
            delivery_log.error_message = (
                "Email backend returned 0."
            )
            delivery_log.save(
                update_fields=[
                    "status",
                    "error_message",
                ],
            )

        return result

    except Exception as exc:
        delivery_log.status = "FAILED"
        delivery_log.error_message = str(exc)
        delivery_log.save(
            update_fields=[
                "status",
                "error_message",
            ],
        )

        raise