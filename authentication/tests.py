import io
import json
import shutil
import tempfile
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .backends import EmailOTPBackend
from .models import EmailOTP, Notification, User


# ── Model tests ──────────────────────────────────────────────────────────────

class UserModelTests(TestCase):
    def test_create_user_email_only(self):
        user = User.objects.create_user(email="test@example.com")
        self.assertEqual(user.email, "test@example.com")
        self.assertFalse(user.has_usable_password())
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)

    def test_create_superuser(self):
        user = User.objects.create_superuser(email="admin@example.com", password="pass")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_create_user_no_email_raises(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(email="")

    def test_default_preferences(self):
        user = User.objects.create_user(email="pref@example.com")
        self.assertEqual(user.dietary_restrictions, [])
        self.assertEqual(user.cuisine_preferences, [])
        self.assertEqual(user.cooking_skill, "intermediate")
        self.assertEqual(user.default_servings, 2)
        self.assertTrue(user.notif_recipe_suggestions)
        self.assertFalse(user.notif_weekly_digest)
        self.assertTrue(user.notif_tips_updates)

    def test_email_is_username_field(self):
        self.assertEqual(User.USERNAME_FIELD, "email")


class EmailOTPModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="otp@example.com")

    def test_generate_creates_6_digit_code(self):
        otp = EmailOTP.generate_for_user(self.user)
        self.assertEqual(len(otp.code), 6)
        self.assertTrue(otp.code.isdigit())
        self.assertFalse(otp.is_used)
        self.assertEqual(otp.ttl_seconds, 300)

    def test_is_not_expired_when_fresh(self):
        otp = EmailOTP.generate_for_user(self.user)
        self.assertFalse(otp.is_expired())

    def test_is_expired_when_old(self):
        otp = EmailOTP.generate_for_user(self.user, ttl_seconds=1)
        otp.created_at = timezone.now() - timedelta(seconds=10)
        otp.save(update_fields=["created_at"])
        self.assertTrue(otp.is_expired())

    def test_str_shows_email_and_status(self):
        otp = EmailOTP.generate_for_user(self.user)
        s = str(otp)
        self.assertIn(self.user.email, s)
        self.assertIn("active", s)

    def test_str_shows_used_when_used(self):
        otp = EmailOTP.generate_for_user(self.user)
        otp.is_used = True
        otp.save()
        self.assertIn("used", str(otp))


class NotificationModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="notif@example.com")

    def test_create_notification_defaults(self):
        n = Notification.objects.create(user=self.user, type="welcome", title="Welcome!")
        self.assertFalse(n.is_read)
        self.assertIsNotNone(n.created_at)

    def test_str_representation(self):
        n = Notification.objects.create(user=self.user, type="system", title="Test")
        s = str(n)
        self.assertIn("system", s)
        self.assertIn(self.user.email, s)


# ── Backend tests ─────────────────────────────────────────────────────────────

class EmailOTPBackendTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="auth@example.com")
        self.backend = EmailOTPBackend()

    def test_valid_otp_returns_user_and_marks_used(self):
        otp = EmailOTP.generate_for_user(self.user)
        result = self.backend.authenticate(None, email="auth@example.com", otp=otp.code)
        self.assertEqual(result, self.user)
        otp.refresh_from_db()
        self.assertTrue(otp.is_used)

    def test_invalid_otp_returns_none(self):
        self.assertIsNone(
            self.backend.authenticate(None, email="auth@example.com", otp="000000")
        )

    def test_expired_otp_returns_none(self):
        otp = EmailOTP.generate_for_user(self.user, ttl_seconds=1)
        otp.created_at = timezone.now() - timedelta(seconds=10)
        otp.save(update_fields=["created_at"])
        self.assertIsNone(
            self.backend.authenticate(None, email="auth@example.com", otp=otp.code)
        )

    def test_used_otp_returns_none(self):
        otp = EmailOTP.generate_for_user(self.user)
        otp.is_used = True
        otp.save()
        self.assertIsNone(
            self.backend.authenticate(None, email="auth@example.com", otp=otp.code)
        )

    def test_missing_email_returns_none(self):
        self.assertIsNone(self.backend.authenticate(None, email=None, otp="123456"))

    def test_missing_otp_returns_none(self):
        self.assertIsNone(self.backend.authenticate(None, email="auth@example.com", otp=None))

    def test_nonexistent_user_returns_none(self):
        self.assertIsNone(
            self.backend.authenticate(None, email="ghost@example.com", otp="123456")
        )

    def test_get_user_by_pk(self):
        self.assertEqual(self.backend.get_user(self.user.pk), self.user)

    def test_get_user_missing_pk_returns_none(self):
        self.assertIsNone(self.backend.get_user(999999))


# ── request_otp ───────────────────────────────────────────────────────────────

class RequestOTPViewTests(TestCase):
    def setUp(self):
        self.client = Client()

    @patch("authentication.views.email_users")
    def test_valid_email_creates_user_and_otp(self, mock_task):
        mock_task.enqueue = MagicMock()
        response = self.client.post(
            reverse("request_otp"),
            data=json.dumps({"email": "new@example.com"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertTrue(User.objects.filter(email="new@example.com").exists())

    @patch("authentication.views.email_users")
    def test_existing_user_gets_new_otp(self, mock_task):
        mock_task.enqueue = MagicMock()
        User.objects.create_user(email="exist@example.com")
        response = self.client.post(
            reverse("request_otp"),
            data=json.dumps({"email": "exist@example.com"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])

    def test_invalid_email_returns_400(self):
        response = self.client.post(
            reverse("request_otp"),
            data=json.dumps({"email": "notanemail"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_missing_email_returns_400(self):
        response = self.client.post(
            reverse("request_otp"),
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_invalid_json_returns_400(self):
        response = self.client.post(
            reverse("request_otp"),
            data="not-json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_get_not_allowed(self):
        response = self.client.get(reverse("request_otp"))
        self.assertEqual(response.status_code, 405)

    @patch("authentication.views.email_users")
    def test_email_send_failure_returns_500(self, mock_task):
        mock_task.enqueue = MagicMock(side_effect=Exception("SMTP error"))
        response = self.client.post(
            reverse("request_otp"),
            data=json.dumps({"email": "fail@example.com"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 500)
        self.assertIn("error", response.json())


# ── verify_otp ────────────────────────────────────────────────────────────────

class VerifyOTPViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(email="verify@example.com")

    def test_valid_otp_logs_in(self):
        otp = EmailOTP.generate_for_user(self.user)
        response = self.client.post(
            reverse("verify_otp"),
            data=json.dumps({"email": "verify@example.com", "code": otp.code}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["email"], "verify@example.com")

    def test_first_login_creates_welcome_notification(self):
        otp = EmailOTP.generate_for_user(self.user)
        self.client.post(
            reverse("verify_otp"),
            data=json.dumps({"email": "verify@example.com", "code": otp.code}),
            content_type="application/json",
        )
        self.assertTrue(
            Notification.objects.filter(user=self.user, type="welcome").exists()
        )

    def test_invalid_otp_returns_400(self):
        response = self.client.post(
            reverse("verify_otp"),
            data=json.dumps({"email": "verify@example.com", "code": "000000"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_missing_code_returns_400(self):
        response = self.client.post(
            reverse("verify_otp"),
            data=json.dumps({"email": "verify@example.com"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_missing_email_returns_400(self):
        response = self.client.post(
            reverse("verify_otp"),
            data=json.dumps({"code": "123456"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_invalid_json_returns_400(self):
        response = self.client.post(
            reverse("verify_otp"),
            data="bad json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)


# ── logout ────────────────────────────────────────────────────────────────────

class LogoutViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(email="logout@example.com")

    def test_logout_returns_ok(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("logout"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])

    def test_get_not_allowed(self):
        response = self.client.get(reverse("logout"))
        self.assertEqual(response.status_code, 405)


# ── upload_avatar ─────────────────────────────────────────────────────────────

class UploadAvatarViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(email="avatar@example.com")
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_unauthenticated_redirects(self):
        response = self.client.post(reverse("upload_avatar"))
        self.assertEqual(response.status_code, 302)

    def test_no_file_returns_400(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("upload_avatar"))
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_invalid_file_type_returns_400(self):
        self.client.force_login(self.user)
        f = SimpleUploadedFile("test.txt", b"some text", content_type="text/plain")
        response = self.client.post(reverse("upload_avatar"), {"avatar": f})
        self.assertEqual(response.status_code, 400)
        self.assertIn("JPEG", response.json()["error"])

    def test_file_too_large_returns_400(self):
        self.client.force_login(self.user)
        large = SimpleUploadedFile(
            "big.png", b"\x89PNG" + b"\x00" * (5 * 1024 * 1024 + 1), content_type="image/png"
        )
        response = self.client.post(reverse("upload_avatar"), {"avatar": large})
        self.assertEqual(response.status_code, 400)
        self.assertIn("5 MB", response.json()["error"])

    @override_settings()
    def test_valid_png_upload(self):
        import os
        from django.conf import settings as django_settings

        django_settings.MEDIA_ROOT = self.tmp_dir
        os.makedirs(os.path.join(self.tmp_dir, "avatars"), exist_ok=True)

        # Minimal valid 1×1 PNG
        png = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
            b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        self.client.force_login(self.user)
        f = SimpleUploadedFile("photo.png", png, content_type="image/png")
        response = self.client.post(reverse("upload_avatar"), {"avatar": f})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertIn("url", response.json())


# ── settings page ─────────────────────────────────────────────────────────────

class SettingsPageViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(email="settings@example.com")

    def test_authenticated_renders_settings(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("settings"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "settings.html")
        self.assertIn("dietary_options", response.context)
        self.assertIn("cuisine_options", response.context)

    def test_unauthenticated_redirects(self):
        response = self.client.get(reverse("settings"))
        self.assertEqual(response.status_code, 302)


# ── set_theme ─────────────────────────────────────────────────────────────────

class SetThemeViewTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_valid_themes(self):
        for theme in ("light", "dark", "system"):
            response = self.client.post(
                reverse("set_theme"),
                data=json.dumps({"theme": theme}),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200, f"theme={theme} failed")
            self.assertTrue(response.json()["ok"])

    def test_invalid_theme_returns_400(self):
        response = self.client.post(
            reverse("set_theme"),
            data=json.dumps({"theme": "purple"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_get_not_allowed(self):
        response = self.client.get(reverse("set_theme"))
        self.assertEqual(response.status_code, 405)


# ── set_language ──────────────────────────────────────────────────────────────

class SetLanguageViewTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_all_valid_languages(self):
        for lang in ("English", "Hindi", "Spanish", "French", "Japanese"):
            response = self.client.post(
                reverse("set_language"),
                data=json.dumps({"language": lang}),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200, f"language={lang} failed")
            self.assertTrue(response.json()["ok"])

    def test_invalid_language_returns_400(self):
        response = self.client.post(
            reverse("set_language"),
            data=json.dumps({"language": "Klingon"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)


# ── set_font ──────────────────────────────────────────────────────────────────

class SetFontViewTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_all_valid_fonts(self):
        for font in ("system", "inter", "lora", "nunito", "poppins"):
            response = self.client.post(
                reverse("set_font"),
                data=json.dumps({"font": font}),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200, f"font={font} failed")

    def test_invalid_font_returns_400(self):
        response = self.client.post(
            reverse("set_font"),
            data=json.dumps({"font": "comic-sans"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)


# ── save_preferences ──────────────────────────────────────────────────────────

class SavePreferencesViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(email="prefs@example.com")

    def test_unauthenticated_redirects(self):
        response = self.client.post(
            reverse("save_preferences"),
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 302)

    def test_save_full_preferences(self):
        self.client.force_login(self.user)
        data = {
            "dietary_restrictions": ["vegan", "gluten-free"],
            "cuisine_preferences": ["italian", "japanese"],
            "cooking_skill": "advanced",
            "default_servings": 4,
        }
        response = self.client.post(
            reverse("save_preferences"),
            data=json.dumps(data),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.user.refresh_from_db()
        self.assertEqual(self.user.cooking_skill, "advanced")
        self.assertEqual(self.user.default_servings, 4)
        self.assertIn("vegan", self.user.dietary_restrictions)
        self.assertIn("italian", self.user.cuisine_preferences)

    def test_invalid_skill_falls_back_to_intermediate(self):
        self.client.force_login(self.user)
        self.client.post(
            reverse("save_preferences"),
            data=json.dumps({"cooking_skill": "wizard", "default_servings": 2}),
            content_type="application/json",
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.cooking_skill, "intermediate")

    def test_servings_clamped_to_max_20(self):
        self.client.force_login(self.user)
        self.client.post(
            reverse("save_preferences"),
            data=json.dumps({"cooking_skill": "beginner", "default_servings": 100}),
            content_type="application/json",
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.default_servings, 20)

    def test_servings_clamped_to_min_1(self):
        self.client.force_login(self.user)
        self.client.post(
            reverse("save_preferences"),
            data=json.dumps({"cooking_skill": "beginner", "default_servings": 0}),
            content_type="application/json",
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.default_servings, 1)

    def test_invalid_dietary_restrictions_filtered(self):
        self.client.force_login(self.user)
        self.client.post(
            reverse("save_preferences"),
            data=json.dumps({
                "dietary_restrictions": ["vegan", "invalid-diet"],
                "cooking_skill": "beginner",
                "default_servings": 2,
            }),
            content_type="application/json",
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.dietary_restrictions, ["vegan"])

    def test_invalid_json_returns_400(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("save_preferences"),
            data="not json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)


# ── update_display_name ───────────────────────────────────────────────────────

class UpdateDisplayNameViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(email="name@example.com")

    def test_update_name(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("update_display_name"),
            data=json.dumps({"name": "Alice"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["name"], "Alice")
        self.user.refresh_from_db()
        self.assertEqual(self.user.name, "Alice")

    def test_name_too_long_returns_400(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("update_display_name"),
            data=json.dumps({"name": "A" * 151}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_empty_name_allowed(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("update_display_name"),
            data=json.dumps({"name": ""}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.name, "")

    def test_unauthenticated_redirects(self):
        response = self.client.post(
            reverse("update_display_name"),
            data=json.dumps({"name": "Bob"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 302)


# ── notifications ─────────────────────────────────────────────────────────────

class NotificationViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(email="notifview@example.com")
        self.notif = Notification.objects.create(
            user=self.user, type="welcome", title="Welcome!", body="Hello", link="/chat/"
        )

    def test_list_authenticated_includes_unread_count(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("list_notifications"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("notifications", data)
        self.assertIn("unread_count", data)
        self.assertEqual(data["unread_count"], 1)
        self.assertEqual(len(data["notifications"]), 1)

    def test_list_returns_required_fields(self):
        self.client.force_login(self.user)
        data = self.client.get(reverse("list_notifications")).json()
        n = data["notifications"][0]
        for field in ("id", "type", "title", "body", "link", "is_read", "created_at"):
            self.assertIn(field, n)

    def test_list_unauthenticated_redirects(self):
        response = self.client.get(reverse("list_notifications"))
        self.assertEqual(response.status_code, 302)

    def test_mark_notification_read(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("mark_notification_read"),
            data=json.dumps({"id": self.notif.id}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.notif.refresh_from_db()
        self.assertTrue(self.notif.is_read)

    def test_mark_all_read(self):
        Notification.objects.create(user=self.user, type="system", title="System")
        self.client.force_login(self.user)
        self.client.post(reverse("mark_all_notifications_read"))
        unread = Notification.objects.filter(user=self.user, is_read=False).count()
        self.assertEqual(unread, 0)

    def test_mark_read_unauthenticated_redirects(self):
        response = self.client.post(
            reverse("mark_notification_read"),
            data=json.dumps({"id": self.notif.id}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 302)

    def test_list_capped_at_20(self):
        for i in range(25):
            Notification.objects.create(user=self.user, type="system", title=f"Notif {i}")
        self.client.force_login(self.user)
        data = self.client.get(reverse("list_notifications")).json()
        self.assertLessEqual(len(data["notifications"]), 20)


# ── save_notification_prefs ───────────────────────────────────────────────────

class SaveNotificationPrefsViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(email="notifprefs@example.com")

    def test_save_prefs(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("save_notification_prefs"),
            data=json.dumps({
                "recipe_suggestions": False,
                "weekly_digest": True,
                "tips_updates": False,
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.user.refresh_from_db()
        self.assertFalse(self.user.notif_recipe_suggestions)
        self.assertTrue(self.user.notif_weekly_digest)
        self.assertFalse(self.user.notif_tips_updates)

    def test_unauthenticated_redirects(self):
        response = self.client.post(
            reverse("save_notification_prefs"),
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 302)

    def test_invalid_json_returns_400(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("save_notification_prefs"),
            data="bad json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
