import json
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from .chat import stream_recipe
from context_processors import VALID_LANGUAGES
from django.contrib.auth.decorators import login_required
from .models import ChatMessage, Chat


def chat(request, chat_id=None):
    if chat_id:
        try:
            chat = Chat.objects.get(id=chat_id, user=request.user)
        except Exception:
            return render(request, "404.html")
        chat_history = ChatMessage.objects.filter(chat=chat).order_by("timestamp")
    else:
        chat_history = []
    print(chat_history)
    return render(request, "chat.html", {"chat_history": chat_history})

@login_required()
def settings_page(request):
    return render(request, "settings.html")

@csrf_protect
@require_http_methods(["POST"])
def set_theme(request):
    data = json.loads(request.body)
    theme = data.get("theme", "light")
    if theme not in ("light", "dark", "system"):
        return JsonResponse({"error": "Invalid theme"}, status=400)
    request.session["theme"] = theme
    return JsonResponse({"ok": True})

@csrf_protect
@require_http_methods(["POST"])
def set_language(request):
    data = json.loads(request.body)
    language = data.get("language", "English")
    if language not in VALID_LANGUAGES:
        return JsonResponse({"error": "Invalid language"}, status=400)
    request.session["language"] = language
    return JsonResponse({"ok": True})

@csrf_protect
@require_http_methods(["POST"])
def chat_message(request):
    """Stream the recipe response as Server-Sent Events."""
    try:
        data = json.loads(request.body)
        dish_name = data.get("message", "").strip()
        chat_id   = data.get("chat_id")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if not dish_name:
        return JsonResponse({"error": "Message cannot be empty"}, status=400)

    language = request.session.get("language", "English")

    # Resolve or create the Chat row (authenticated users only)
    chat_obj = None
    if request.user.is_authenticated:
        if chat_id:
            chat_obj = Chat.objects.filter(id=chat_id, user=request.user).first()
        if chat_obj is None:
            chat_obj = Chat.objects.create(title=dish_name[:255], user=request.user)
        ChatMessage.objects.create(chat=chat_obj, sender="user", content=dish_name)

    def event_stream():
        try:
            for token in stream_recipe(dish_name, language):
                yield f"data: {json.dumps({'token': token})}\n\n"

            done_payload = {"done": True}
            if chat_obj:
                done_payload["chat_id"] = str(chat_obj.id)
                done_payload["chat_title"] = chat_obj.title
            yield f"data: {json.dumps(done_payload)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


@csrf_protect
@require_http_methods(["POST"])
def save_bot_message(request):
    """Save the rendered HTML of a bot reply after streaming completes."""
    try:
        data = json.loads(request.body)
        chat_id = data.get("chat_id", "").strip()
        html    = data.get("content", "").strip()
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if not chat_id or not html:
        return JsonResponse({"error": "chat_id and content are required"}, status=400)

    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required"}, status=401)

    chat_obj = Chat.objects.filter(id=chat_id, user=request.user).first()
    if not chat_obj:
        return JsonResponse({"error": "Chat not found"}, status=404)

    ChatMessage.objects.create(chat=chat_obj, sender="bot", content=html)
    return JsonResponse({"ok": True})
