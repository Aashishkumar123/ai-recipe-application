from django.urls import path
from .import views

urlpatterns = [
    path("", views.chat, name="chat"),
    path("<uuid:chat_id>/", views.chat, name="chat-history"),
    path("api/message/", views.chat_message, name="message"),
    path("api/save-bot-message/", views.save_bot_message, name="save_bot_message"),
]