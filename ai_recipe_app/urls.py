from django.urls import path
from .import views

urlpatterns = [
    path("", views.chat, name="index"),
    path("api/message/", views.chat_message, name="message"),
]