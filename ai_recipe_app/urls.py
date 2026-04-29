from django.urls import path
from .import views

urlpatterns = [
    path("", views.chat, name="chat"),
    path("<uuid:chat_id>/", views.chat, name="chat-history"),
    path("public/<uuid:chat_id>/", views.public_chat, name="public-chat"),
    path("api/message/", views.chat_message, name="message"),
    path("api/save-bot-message/", views.save_bot_message, name="save_bot_message"),
    path("api/rename-chat/", views.rename_chat, name="rename_chat"),
    path("api/delete-chat/", views.delete_chat, name="delete_chat"),
    path("api/download-pdf/", views.download_pdf, name="download_pdf"),
    path("api/share-chat/", views.share_chat, name="share_chat"),
    path("api/youtube-videos/", views.youtube_videos, name="youtube_videos"),
]