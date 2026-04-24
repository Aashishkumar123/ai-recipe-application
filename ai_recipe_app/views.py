import json
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from .chat import stream_recipe
from .context_processors import VALID_LANGUAGES
from django.contrib.auth.decorators import login_required

def chat(request):
    return render(request, "chat.html")

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
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if not dish_name:
        return JsonResponse({"error": "Message cannot be empty"}, status=400)

    language = request.session.get("language", "English")

    def event_stream():
        try:
            for token in stream_recipe(dish_name, language):
                payload = json.dumps({"token": token})
                yield f"data: {payload}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    response = StreamingHttpResponse(
        event_stream(),
        content_type="text/event-stream",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
