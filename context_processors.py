from django.utils import timezone
from datetime import timedelta

VALID_LANGUAGES = ("English", "Hindi", "Spanish", "French", "Japanese")

def context_processors(request):
    ctx = {
        "theme": request.session.get("theme", "light"),
        "language": request.session.get("language", "English"),
        "name": request.user.name if request.user.is_authenticated else "Guest",
        "chats_today": [],
        "chats_yesterday": [],
        "chats_week": [],
        "chats_older": [],
        "unread_notifications_count": 0,
    }
    if request.user.is_authenticated:
        now = timezone.now()
        today_start     = now.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start = today_start - timedelta(days=1)
        week_start      = today_start - timedelta(days=7)

        chats = list(request.user.chats.order_by("-created_at"))
        for chat in chats:
            if chat.created_at >= today_start:
                ctx["chats_today"].append(chat)
            elif chat.created_at >= yesterday_start:
                ctx["chats_yesterday"].append(chat)
            elif chat.created_at >= week_start:
                ctx["chats_week"].append(chat)
            else:
                ctx["chats_older"].append(chat)

        from authentication.models import Notification
        ctx["unread_notifications_count"] = Notification.objects.filter(
            user=request.user, is_read=False
        ).count()
    return ctx
