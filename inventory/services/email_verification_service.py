from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone


def build_verification_link(customer):
    base_url = getattr(settings, 'FRONTEND_BASE_URL', 'http://localhost:3000').rstrip('/')
    token = customer.email_verification_token
    uid = customer.user.id if customer.user else ''
    return f"{base_url}/verify-email?token={token}&uid={uid}"


def send_verification_email(customer):
    if not customer or not customer.user or not customer.user.email:
        return

    if not customer.email_verification_token:
        customer.issue_email_verification()

    verification_link = build_verification_link(customer)
    subject = "Verify your email address"
    message = (
        "Thanks for creating an account. Please verify your email address by clicking the link below:\n\n"
        f"{verification_link}\n\n"
        "If you did not create this account, you can ignore this email."
    )

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[customer.user.email],
        fail_silently=False,
    )

    customer.email_verification_sent_at = timezone.now()
    customer.save(update_fields=['email_verification_sent_at'])
