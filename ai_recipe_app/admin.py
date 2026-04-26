from django.contrib import admin
from .models import Chat, ChatMessage

@admin.register(Chat)
class ChatAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'created_at', 'updated_at', 'user__email')
    search_fields = ('title', 'user__email')
    list_filter = ('created_at', 'updated_at', 'user__email')

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('chat', 'sender', 'timestamp')
    search_fields = ('content', 'chat__title', 'sender')
    list_filter = ('sender', 'timestamp')
    ordering = ('timestamp',)
