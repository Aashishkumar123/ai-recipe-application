import re
import json
from io import BytesIO
from django.http import JsonResponse, StreamingHttpResponse, HttpResponse
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
    chat_obj = None
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
    return render(request, "chat.html", {"chat_history": chat_history, "chat_obj": chat_obj})


def public_chat(request, chat_id):
    """Read-only public view — no authentication required."""
    try:
        chat_obj = Chat.objects.get(id=chat_id, is_public=True)
    except Chat.DoesNotExist:
        return render(request, "404.html", status=404)

    # Notify the owner when someone (not themselves) views their shared chat
    viewer = request.user
    if viewer.is_authenticated and viewer != chat_obj.user:
        from authentication.models import Notification
        already_notified = Notification.objects.filter(
            user=chat_obj.user, type="shared_chat_viewed", link=f"/chat/{chat_id}/"
        ).exists()
        if not already_notified:
            Notification.objects.create(
                user=chat_obj.user,
                type="shared_chat_viewed",
                title="Someone viewed your shared recipe",
                body=f'Your chat "{chat_obj.title}" was viewed by another user.',
                link=f"/chat/{chat_id}/",
            )

    chat_history = ChatMessage.objects.filter(chat=chat_obj).order_by("timestamp")
    return render(request, "shared_chat.html", {"chat_obj": chat_obj, "chat_history": chat_history})

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
            # Emit chat_id first so the client can save partial content on abort
            if chat_obj:
                yield f"data: {json.dumps({'chat_id': str(chat_obj.id), 'chat_title': chat_obj.title})}\n\n"

            for token in stream_recipe(dish_name, language, lc_history, user=request.user):
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


@csrf_protect
@require_http_methods(["POST"])
def download_pdf(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required"}, status=401)

    try:
        data         = json.loads(request.body)
        html_content = data.get("html", "").strip()
        title        = data.get("title", "Recipe").strip()
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if not html_content:
        return JsonResponse({"error": "No content"}, status=400)

    from fpdf import FPDF

    # Helvetica only covers Latin-1 (U+0000–U+00FF) — strip everything outside that range
    clean = re.sub(r"[^\x00-\xFF]", "", html_content)
    # Remove toolbar divs injected by chat UI
    clean = re.sub(r'<div[^>]*class="[^"]*mt-1[^"]*"[^>]*>.*?</div>', "", clean, flags=re.DOTALL)
    # Strip links/formatting tags, keep their text
    for tag in ("a", "strong", "b", "em", "i", "code", "span"):
        clean = re.sub(rf'<{tag}[^>]*>(.*?)</{tag}>', r'\1', clean, flags=re.DOTALL)

    def _text(s):
        """Strip remaining HTML tags and normalise whitespace."""
        return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', s)).strip()

    # Parse HTML into a flat list of (type, content) pairs
    elements = []
    for m in re.finditer(
        r'<(h1|h2|h3|p|ul|ol|blockquote)(?:\s[^>]*)?>(.+?)</\1>',
        clean, re.DOTALL | re.IGNORECASE,
    ):
        tag, body = m.group(1).lower(), m.group(2)
        if tag in ("h1", "h2", "h3"):
            t = _text(body)
            if t:
                elements.append((tag, t))
        elif tag == "p":
            t = _text(body)
            if t:
                elements.append(("p", t))
        elif tag == "ul":
            for li in re.findall(r'<li[^>]*>(.*?)</li>', body, re.DOTALL):
                t = _text(li)
                if t:
                    elements.append(("li", t))
        elif tag == "ol":
            for idx, li in enumerate(re.findall(r'<li[^>]*>(.*?)</li>', body, re.DOTALL), 1):
                t = _text(li)
                if t:
                    elements.append(("oli", (idx, t)))
        elif tag == "blockquote":
            t = _text(body)
            if t:
                elements.append(("blockquote", t))

    try:
        pdf = FPDF()
        pdf.set_margins(20, 22, 20)
        pdf.set_auto_page_break(auto=True, margin=22)
        pdf.add_page()
        W = pdf.w - pdf.l_margin - pdf.r_margin

        # ── Brand header ──────────────────────────────────────────────
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(249, 115, 22)
        pdf.cell(0, 6, "Recipe Chef", new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(253, 186, 116)
        pdf.set_line_width(0.5)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        pdf.ln(7)

        # ── Content ───────────────────────────────────────────────────
        for etype, content in elements:

            if etype == "h1":
                pdf.set_font("Helvetica", "B", 22)
                pdf.set_text_color(194, 65, 12)
                pdf.multi_cell(W, 12, content, new_x="LMARGIN", new_y="NEXT")
                pdf.ln(2)

            elif etype == "h2":
                pdf.ln(5)
                pdf.set_font("Helvetica", "B", 12)
                pdf.set_text_color(17, 24, 39)
                pdf.multi_cell(W, 7, content, new_x="LMARGIN", new_y="NEXT")
                pdf.set_draw_color(229, 231, 235)
                pdf.set_line_width(0.3)
                pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
                pdf.ln(3)

            elif etype == "h3":
                pdf.ln(3)
                pdf.set_font("Helvetica", "B", 10)
                pdf.set_text_color(107, 114, 128)
                pdf.multi_cell(W, 6, content, new_x="LMARGIN", new_y="NEXT")
                pdf.ln(1)

            elif etype == "p":
                pdf.set_font("Helvetica", "", 10)
                pdf.set_text_color(107, 114, 128)
                pdf.multi_cell(W, 6, content, new_x="LMARGIN", new_y="NEXT")
                pdf.ln(2)

            elif etype == "li":
                pdf.set_x(pdf.l_margin)
                pdf.set_font("Helvetica", "B", 14)
                pdf.set_text_color(249, 115, 22)
                pdf.cell(6, 6, "\xb7")          # middle dot bullet
                pdf.set_font("Helvetica", "", 10)
                pdf.set_text_color(55, 65, 81)
                pdf.multi_cell(W - 6, 6, content, new_x="LMARGIN", new_y="NEXT")
                pdf.ln(0.5)

            elif etype == "oli":
                num, text = content
                pdf.set_x(pdf.l_margin)
                pdf.set_font("Helvetica", "B", 10)
                pdf.set_text_color(249, 115, 22)
                num_w = 9
                pdf.cell(num_w, 6.5, f"{num}.")
                pdf.set_font("Helvetica", "", 10)
                pdf.set_text_color(55, 65, 81)
                pdf.multi_cell(W - num_w, 6.5, text, new_x="LMARGIN", new_y="NEXT")
                pdf.ln(1.5)

            elif etype == "blockquote":
                pdf.ln(3)
                y0 = pdf.get_y()
                pdf.set_x(pdf.l_margin + 8)
                pdf.set_font("Helvetica", "I", 10)
                pdf.set_text_color(146, 64, 14)
                pdf.multi_cell(W - 8, 6, content, new_x="LMARGIN", new_y="NEXT")
                y1 = pdf.get_y()
                pdf.set_draw_color(249, 115, 22)
                pdf.set_line_width(2)
                pdf.line(pdf.l_margin + 2, y0, pdf.l_margin + 2, y1)
                pdf.ln(3)

        # ── Footer ────────────────────────────────────────────────────
        pdf.set_y(-14)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(156, 163, 175)
        pdf.cell(0, 6, "Generated by Recipe Chef", align="C")

        buffer = BytesIO()
        pdf.output(buffer)
    except Exception:
        logger.exception("download_pdf | fpdf2 error user={}", request.user)
        return JsonResponse({"error": "PDF generation failed"}, status=500)

    safe_name = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "recipe"
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{safe_name}.pdf"'
    logger.info("PDF downloaded | user={} title={!r}", request.user, title)
    return response


@csrf_protect
@require_http_methods(["POST"])
def share_chat(request):
    """Set a chat public or private and return its public URL."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required"}, status=401)

    try:
        data = json.loads(request.body)
        chat_id   = data.get("chat_id", "").strip()
        make_public = data.get("public")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if not chat_id or make_public is None:
        return JsonResponse({"error": "chat_id and public are required"}, status=400)

    chat_obj = Chat.objects.filter(id=chat_id, user=request.user).first()
    if not chat_obj:
        return JsonResponse({"error": "Chat not found"}, status=404)

    chat_obj.is_public = bool(make_public)
    chat_obj.save(update_fields=["is_public"])
    logger.info("Chat share toggled | chat_id={} public={} user={}", chat_id, chat_obj.is_public, request.user)

    public_url = request.build_absolute_uri(f"/chat/public/{chat_obj.id}/") if chat_obj.is_public else None
    return JsonResponse({"ok": True, "is_public": chat_obj.is_public, "public_url": public_url})
