from accounts.models import EmailDeliveryLog
from accounts.services.email_service import send_notification_email


def retry_failed_email(delivery_log_id, max_retries=3):
    delivery_log = EmailDeliveryLog.objects.get(
        id=delivery_log_id
    )

    if delivery_log.status == "SENT":
        return {
            "success": True,
            "message": "Email has already been sent.",
            "delivery_log": delivery_log,
        }

    if delivery_log.attempt_count >= max_retries:
        return {
            "success": False,
            "message": "Maximum retry attempts reached.",
            "delivery_log": delivery_log,
        }

    try:
        result = send_notification_email(
            recipient_email=delivery_log.recipient_email,
            subject=delivery_log.subject,
            template_name=delivery_log.template_name,
            context=delivery_log.context,
            notification_type=delivery_log.notification_type,
            delivery_log=delivery_log,
        )

        if result:
            return {
                "success": True,
                "message": "Email retry successful.",
                "delivery_log": delivery_log,
            }

    except Exception as exc:
        return {
            "success": False,
            "message": "Email retry failed.",
            "delivery_log": delivery_log,
            "error": str(exc),
        }

    return {
        "success": False,
        "message": "Email retry failed.",
        "delivery_log": delivery_log,
    }