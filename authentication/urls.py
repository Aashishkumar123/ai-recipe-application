from django.urls import path
from . import views

urlpatterns = [
    path("request-otp/", views.request_otp, name="request_otp"),
    path("verify-otp/",  views.verify_otp,  name="verify_otp"),
    path("logout/",       views.logout_view,  name="logout"),
    path("upload-avatar/", views.upload_avatar, name="upload_avatar"),
    path("settings/", views.settings_page, name="settings"),
    path("api/set-theme/", views.set_theme, name="set_theme"),
    path("api/set-language/", views.set_language, name="set_language"),
    path("api/set-font/", views.set_font, name="set_font"),
    path("google/login/",    views.google_login,    name="google_login"),
    path("google/callback/", views.google_callback, name="google_callback"),
    path("api/save-preferences/", views.save_preferences, name="save_preferences"),
    path("api/notifications/", views.list_notifications, name="list_notifications"),
    path("api/notifications/mark-read/", views.mark_notification_read, name="mark_notification_read"),
    path("api/notifications/mark-all-read/", views.mark_all_notifications_read, name="mark_all_notifications_read"),
]
