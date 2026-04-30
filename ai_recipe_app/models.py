from django.db import models
from uuid import uuid4
import hashlib

class Chat(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    title=models.CharField(max_length=255)
    is_public=models.BooleanField(default=False)
    is_pinned=models.BooleanField(default=False)
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


class StepDetail(models.Model):
    """Cached LLM explanation for a single instruction step."""
    key        = models.CharField(max_length=64, unique=True)  # sha256 of recipe|step
    step_text  = models.TextField()
    detail     = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def make_key(recipe: str, step: str) -> str:
        return hashlib.sha256(f"{recipe.lower()}|{step.lower()}".encode()).hexdigest()

    def __str__(self):
        return f"StepDetail({self.key[:8]}…)"
