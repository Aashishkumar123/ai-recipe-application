import json
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from langchain_core.messages import HumanMessage, AIMessage
from loguru import logger
from .chat import stream_recipe
from .models import ChatMessage, Chat
from .utils import html_to_text

logger.debug("Importing ai_recipe_app.views")


def chat(request, chat_id=None):
    logger.debug("chat view | user={} chat_id={}", request.user, chat_id)
    if chat_id:
        try:
            chat_obj = Chat.objects.get(id=chat_id, user=request.user)
        except Exception:
            logger.warning("Chat not found or forbidden | chat_id={} user={}", chat_id, request.user)
            return render(request, "404.html")
        chat_history = ChatMessage.objects.filter(chat=chat_obj).order_by("timestamp")
        logger.debug("Loaded chat history | chat_id={} messages={}", chat_id, chat_history.count())
    else:
        chat_history = []
    return render(request, "chat.html", {"chat_history": chat_history})

@csrf_protect
@require_http_methods(["POST"])
def chat_message(request):
    """Stream the recipe response as Server-Sent Events."""
    try:
        data = json.loads(request.body)
        dish_name = data.get("message", "").strip()
        chat_id   = data.get("chat_id")
    except json.JSONDecodeError:
        logger.warning("chat_message | invalid JSON from user={}", request.user)
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if not dish_name:
        logger.warning("chat_message | empty message from user={}", request.user)
        return JsonResponse({"error": "Message cannot be empty"}, status=400)

    language = request.session.get("language", "English")
    logger.info(
        "chat_message | user={} dish={!r} chat_id={} language={}",
        request.user, dish_name, chat_id, language,
    )

    # Resolve or create the Chat row (authenticated users only)
    chat_obj = None
    lc_history = []
    if request.user.is_authenticated:
        if chat_id:
            chat_obj = Chat.objects.filter(id=chat_id, user=request.user).first()
            if chat_obj:
                logger.debug("Resumed existing chat | chat_id={}", chat_id)
            else:
                logger.warning("chat_id {} not found for user={} — creating new", chat_id, request.user)

        if chat_obj is None:
            chat_obj = Chat.objects.create(title=dish_name[:255], user=request.user)
            logger.info("New Chat created | id={} title={!r} user={}", chat_obj.id, chat_obj.title, request.user)
        else:
            past = ChatMessage.objects.filter(chat=chat_obj).order_by("timestamp")[:10]
            for msg in past:
                if msg.sender == "user":
                    lc_history.append(HumanMessage(content=msg.content))
                else:
                    lc_history.append(AIMessage(content=html_to_text(msg.content)))
            logger.debug("History loaded | chat_id={} turns={}", chat_obj.id, len(lc_history))

        ChatMessage.objects.create(chat=chat_obj, sender="user", content=dish_name)
        logger.debug("User message saved | chat_id={}", chat_obj.id)

    def event_stream():
        try:
            for token in stream_recipe(dish_name, language, lc_history):
                yield f"data: {json.dumps({'token': token})}\n\n"

            done_payload = {"done": True}
            if chat_obj:
                done_payload["chat_id"] = str(chat_obj.id)
                done_payload["chat_title"] = chat_obj.title
            yield f"data: {json.dumps(done_payload)}\n\n"
        except Exception as e:
            logger.error("event_stream error | dish={!r} error={}", dish_name, e)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


@csrf_protect
@require_http_methods(["POST"])
def rename_chat(request):
    try:
        data = json.loads(request.body)
        chat_id = data.get("chat_id", "").strip()
        title   = data.get("title", "").strip()
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required"}, status=401)
    if not chat_id or not title:
        return JsonResponse({"error": "chat_id and title are required"}, status=400)

    chat_obj = Chat.objects.filter(id=chat_id, user=request.user).first()
    if not chat_obj:
        return JsonResponse({"error": "Chat not found"}, status=404)

    chat_obj.title = title[:255]
    chat_obj.save(update_fields=["title"])
    logger.info("Chat renamed | chat_id={} user={} title={!r}", chat_id, request.user, title)
    return JsonResponse({"ok": True})


@csrf_protect
@require_http_methods(["POST"])
def delete_chat(request):
    try:
        data    = json.loads(request.body)
        chat_id = data.get("chat_id", "").strip()
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required"}, status=401)
    if not chat_id:
        return JsonResponse({"error": "chat_id is required"}, status=400)

    chat_obj = Chat.objects.filter(id=chat_id, user=request.user).first()
    if not chat_obj:
        return JsonResponse({"error": "Chat not found"}, status=404)

    chat_obj.delete()
    logger.info("Chat deleted | chat_id={} user={}", chat_id, request.user)
    return JsonResponse({"ok": True})


@csrf_protect
@require_http_methods(["POST"])
def save_bot_message(request):
    """Save the rendered HTML of a bot reply after streaming completes."""
    try:
        data = json.loads(request.body)
        chat_id = data.get("chat_id", "").strip()
        html    = data.get("content", "").strip()
    except json.JSONDecodeError:
        logger.warning("save_bot_message | invalid JSON from user={}", request.user)
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if not chat_id or not html:
        logger.warning("save_bot_message | missing fields user={}", request.user)
        return JsonResponse({"error": "chat_id and content are required"}, status=400)

    if not request.user.is_authenticated:
        logger.warning("save_bot_message | unauthenticated request for chat_id={}", chat_id)
        return JsonResponse({"error": "Authentication required"}, status=401)

    chat_obj = Chat.objects.filter(id=chat_id, user=request.user).first()
    if not chat_obj:
        logger.warning("save_bot_message | chat not found chat_id={} user={}", chat_id, request.user)
        return JsonResponse({"error": "Chat not found"}, status=404)

    ChatMessage.objects.create(chat=chat_obj, sender="bot", content=html)
    logger.success("Bot message saved | chat_id={} user={}", chat_id, request.user)
    return JsonResponse({"ok": True})
