import json
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from .chat import stream_recipe

def chat(request):
    return render(request, "chat.html")

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

    def event_stream():
        try:
            for token in stream_recipe(dish_name):
                # SSE format: each message is "data: {json}\n\n"
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
    response["X-Accel-Buffering"] = "no"  # disable nginx buffering if deployed
    return response
