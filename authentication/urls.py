from django.urls import path
from . import views

urlpatterns = [
    path("request-otp/", views.request_otp, name="request_otp"),
    path("verify-otp/",  views.verify_otp,  name="verify_otp"),
    path("logout/",       views.logout_view,  name="logout"),
    path("upload-avatar/", views.upload_avatar, name="upload_avatar"),
]
