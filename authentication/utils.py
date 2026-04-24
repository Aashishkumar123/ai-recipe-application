from django.core.mail import send_mail
from django.tasks import task
from django.conf import settings


@task
def email_users(email, otp):
    send_mail(
            subject="Your Recipe Chef verification code",
            message=(
                f"Hi,\n\n"
                f"Your verification code is: {otp}\n\n"
                f"This code expires in 5 minutes. If you didn't request this, you can ignore this email.\n\n"
                f"— Recipe Chef"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
