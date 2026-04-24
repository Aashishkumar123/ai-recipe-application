from django.conf import settings
from django.db import models
from django.utils import timezone
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
import secrets
import datetime


class UserManager(BaseUserManager):
	"""Custom user manager where email is the unique identifiers
	for authentication instead of usernames."""

	use_in_migrations = True

	def _create_user(self, email, password, **extra_fields):
		"""Create and save a User with the given email and password."""
		if not email:
			raise ValueError('The given email must be set')
		email = self.normalize_email(email)
		user = self.model(email=email, **extra_fields)
		if password:
			user.set_password(password)
		else:
			user.set_unusable_password()
		user.save(using=self._db)
		return user

	def create_user(self, email, password=None, **extra_fields):
		extra_fields.setdefault('is_staff', False)
		extra_fields.setdefault('is_superuser', False)
		return self._create_user(email, password, **extra_fields)

	def create_superuser(self, email, password, **extra_fields):
		extra_fields.setdefault('is_staff', True)
		extra_fields.setdefault('is_superuser', True)

		if extra_fields.get('is_staff') is not True:
			raise ValueError('Superuser must have is_staff=True.')
		if extra_fields.get('is_superuser') is not True:
			raise ValueError('Superuser must have is_superuser=True.')

		return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
	"""Custom User model that uses email as the unique identifier and
	does not include a username field."""

	email = models.EmailField('email address', unique=True)
	first_name = models.CharField('first name', max_length=150, blank=True)
	last_name = models.CharField('last name', max_length=150, blank=True)
	profile_picture = models.ImageField(upload_to='avatars/', blank=True, null=True, default="avatars/default.png")
	is_staff = models.BooleanField(
		'staff status',
		default=False,
		help_text='Designates whether the user can log into this admin site.',
	)
	is_active = models.BooleanField(
		'active',
		default=True,
		help_text='Designates whether this user should be treated as active. '
				  'Unselect this instead of deleting accounts.',
	)
	date_joined = models.DateTimeField('date joined', default=timezone.now)

	objects = UserManager()

	EMAIL_FIELD = 'email'
	USERNAME_FIELD = 'email'
	REQUIRED_FIELDS = []

	class Meta:
		verbose_name = 'user'
		verbose_name_plural = 'users'

	def get_full_name(self):
		full = f"{self.first_name} {self.last_name}".strip()
		return full or self.email

	def get_short_name(self):
		return self.first_name or self.email


class EmailOTP(models.Model):
	"""One-time password (OTP) record associated with a user.

	This simple model stores a short numeric/text code and an expiry time.
	Your views/services should create an EmailOTP instance and send the code
	to the user's email. Verification is performed in the authentication
	backend (see `auth/backends.py`).
	"""

	user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='otps')
	code = models.CharField(max_length=10)
	created_at = models.DateTimeField(auto_now_add=True)
	is_used = models.BooleanField(default=False)
	ttl_seconds = models.IntegerField(default=300)  # 5 minutes by default

	class Meta:
		indexes = [models.Index(fields=['user', 'code']), models.Index(fields=['created_at'])]

	def __str__(self):
		return f"OTP for {self.user.email} - {'used' if self.is_used else 'active'}"

	def is_expired(self):
		return timezone.now() > self.created_at + datetime.timedelta(seconds=self.ttl_seconds)

	@classmethod
	def generate_for_user(cls, user, length=6, ttl_seconds=300):
		"""Create and return a new OTP for the given user.

		Uses a cryptographically secure generator for the code.
		"""
		# Use digits only by default
		code = ''.join(secrets.choice('0123456789') for _ in range(length))
		otp = cls.objects.create(user=user, code=code, ttl_seconds=ttl_seconds)
		return otp

