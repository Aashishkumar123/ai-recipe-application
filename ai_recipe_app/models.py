from django.db import models
from uuid import uuid4

class Chat(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    title=models.CharField(max_length=255)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    user=models.ForeignKey('authentication.User', on_delete=models.CASCADE, related_name='chats')

    def __str__(self):
        return self.title

class ChatMessage(models.Model):
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name='messages')
    sender = models.CharField(max_length=10, choices=[('user', 'User'), ('bot', 'Bot')])
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender} at {self.timestamp}: {self.content[:50]}"
