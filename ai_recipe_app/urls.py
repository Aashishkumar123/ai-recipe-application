from django.urls import path
from .import views

urlpatterns = [
    path("", views.chat, name="chat"),
    path("<uuid:chat_id>/", views.chat, name="chat-history"),
    path("settings/", views.settings_page, name="settings"),
    path("api/message/", views.chat_message, name="message"),
    path("api/save-bot-message/", views.save_bot_message, name="save_bot_message"),
    path("api/set-theme/", views.set_theme, name="set_theme"),
    path("api/set-language/", views.set_language, name="set_language"),
]