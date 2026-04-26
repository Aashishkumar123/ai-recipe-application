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
]
