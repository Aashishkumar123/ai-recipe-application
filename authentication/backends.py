from django.contrib.auth.backends import BaseBackend
from django.contrib.auth import get_user_model
from .models import EmailOTP


UserModel = get_user_model()


class EmailOTPBackend(BaseBackend):
    """Authenticate using email and a one-time code stored in EmailOTP.

    Expected credentials: {'email': 'user@example.com', 'otp': '123456'}
    """

    def authenticate(self, request, email=None, otp=None, **kwargs):
        if email is None or otp is None:
            return None
        try:
            user = UserModel.objects.get(email__iexact=email)
        except UserModel.DoesNotExist:
            return None

        # Find the latest matching OTP for this user that is not used
        otps = EmailOTP.objects.filter(user=user, code=otp, is_used=False).order_by('-created_at')
        for candidate in otps:
            if not candidate.is_expired():
                candidate.is_used = True
                candidate.save(update_fields=['is_used'])
                return user
        return None

    def get_user(self, user_id):
        try:
            return UserModel.objects.get(pk=user_id)
        except UserModel.DoesNotExist:
            return None
