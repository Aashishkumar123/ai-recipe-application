import json
import secrets
from urllib.parse import urlencode
import httpx
from django.core.files.base import ContentFile
from django.conf import settings as django_settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from context_processors import VALID_LANGUAGES
from .models import EmailOTP, Notification
from .utils import email_users

User = get_user_model()

# ── Google OAuth ──────────────────────────────────────────────
_GOOGLE_AUTH_URL     = "https://accounts.google.com/o/oauth2/auth"
_GOOGLE_TOKEN_URL    = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

def google_login(request):
    state = secrets.token_urlsafe(16)
    request.session["google_oauth_state"] = state
    params = {
        "client_id":     django_settings.GOOGLE_CLIENT_ID,
        "redirect_uri":  django_settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope":         "openid email profile",
        "state":         state,
        "access_type":   "online",
    }
    return redirect(f"{_GOOGLE_AUTH_URL}?{urlencode(params)}")

def google_callback(request):
    if request.GET.get("error"):
        return redirect("/chat/")
    code  = request.GET.get("code")
    state = request.GET.get("state")
    if not code or state != request.session.pop("google_oauth_state", None):
        return redirect("/chat/")
    try:
        token_res = httpx.post(_GOOGLE_TOKEN_URL, data={
            "code":          code,
            "client_id":     django_settings.GOOGLE_CLIENT_ID,
            "client_secret": django_settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri":  django_settings.GOOGLE_REDIRECT_URI,
            "grant_type":    "authorization_code",
        }, timeout=10)
        access_token = token_res.json().get("access_token")
        if not access_token:
            return redirect("/chat/")
        userinfo = httpx.get(_GOOGLE_USERINFO_URL,
                             headers={"Authorization": f"Bearer {access_token}"},
                             timeout=10).json()
        email = userinfo.get("email")
        if not email:
            return redirect("/chat/")
        name        = userinfo.get("name", "")
        picture_url = userinfo.get("picture", "")

        user, created = User.objects.get_or_create(email=email, defaults={"name": name})

        update_fields = []
        if not user.name and name:
            user.name = name
            update_fields.append("name")

        # Save profile picture if user has no custom one (default or blank)
        is_default = not user.profile_picture or "default.png" in str(user.profile_picture)
        if picture_url and (created or is_default):
            try:
                img_res = httpx.get(picture_url, timeout=10, follow_redirects=True)
                if img_res.status_code == 200:
                    ext = "jpg"
                    fname = f"google_{user.pk}.{ext}"
                    user.profile_picture.save(fname, ContentFile(img_res.content), save=False)
                    update_fields.append("profile_picture")
            except Exception:
                pass

        if update_fields:
            user.save(update_fields=update_fields)

        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    except Exception:
        pass
    return redirect("/chat/")


@csrf_protect
@require_http_methods(["POST"])
def request_otp(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid request"}, status=400)

    email = data.get("email", "").strip().lower()
    if not email or "@" not in email:
        return JsonResponse({"error": "Please enter a valid email address."}, status=400)

    user, _ = User.objects.get_or_create(email=email)
    otp = EmailOTP.generate_for_user(user)

    try:
       email_users.enqueue(email=email, otp=otp.code)
    except Exception as e:
        print(e)
        return JsonResponse({"error": "Failed to send email. Please try again."}, status=500)

    return JsonResponse({"ok": True})


@csrf_protect
@require_http_methods(["POST"])
def verify_otp(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid request"}, status=400)

    email = data.get("email", "").strip().lower()
    code = data.get("code", "").strip()

    if not email or not code:
        return JsonResponse({"error": "Email and code are required."}, status=400)

    user = authenticate(request, email=email, otp=code)
    if user is None:
        return JsonResponse({"error": "Invalid or expired code. Please try again."}, status=400)

    is_new = user.last_login is None
    login(request, user)
    if is_new:
        Notification.objects.create(
            user=user,
            type="welcome",
            title="Welcome to Recipe Chef! 🍳",
            body="Your personalised recipe assistant is ready. Ask me anything — from quick weeknight dinners to weekend showstoppers.",
            link="/chat/",
        )
    return JsonResponse({"ok": True, "name": user.name, "email": user.email})


@csrf_protect
@require_http_methods(["POST"])
def logout_view(request):
    logout(request)
    return JsonResponse({"ok": True})


@login_required
@csrf_protect
@require_http_methods(["POST"])
def upload_avatar(request):
    file = request.FILES.get("avatar")
    if not file:
        return JsonResponse({"error": "No file provided."}, status=400)

    allowed = {"image/jpeg", "image/png", "image/webp", "image/gif"}
    if file.content_type not in allowed:
        return JsonResponse({"error": "Only JPEG, PNG, WebP or GIF images are allowed."}, status=400)

    if file.size > 5 * 1024 * 1024:
        return JsonResponse({"error": "Image must be smaller than 5 MB."}, status=400)

    user = request.user
    if user.profile_picture:
        user.profile_picture.delete(save=False)

    user.profile_picture.save(file.name, file, save=True)
    return JsonResponse({"ok": True, "url": request.build_absolute_uri(user.profile_picture.url)})


DIETARY_OPTIONS  = [
    ("vegan",        "Vegan"),
    ("vegetarian",   "Vegetarian"),
    ("gluten-free",  "Gluten-Free"),
    ("dairy-free",   "Dairy-Free"),
    ("nut-free",     "Nut-Free"),
    ("halal",        "Halal"),
    ("kosher",       "Kosher"),
    ("low-carb",     "Low-Carb"),
]
CUISINE_OPTIONS = [
    ("italian",       "Italian"),
    ("indian",        "Indian"),
    ("japanese",      "Japanese"),
    ("mexican",       "Mexican"),
    ("thai",          "Thai"),
    ("mediterranean", "Mediterranean"),
    ("chinese",       "Chinese"),
    ("american",      "American"),
    ("french",        "French"),
    ("korean",        "Korean"),
]

@login_required()
def settings_page(request):
    return render(request, "settings.html", {
        "dietary_options": DIETARY_OPTIONS,
        "cuisine_options":  CUISINE_OPTIONS,
    })

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

VALID_FONTS = {"system", "inter", "lora", "nunito", "poppins"}

@csrf_protect
@require_http_methods(["POST"])
def set_font(request):
    data = json.loads(request.body)
    font = data.get("font", "system")
    if font not in VALID_FONTS:
        return JsonResponse({"error": "Invalid font"}, status=400)
    request.session["font"] = font
    return JsonResponse({"ok": True})


VALID_DIETARY  = {"vegan", "vegetarian", "gluten-free", "dairy-free", "nut-free", "halal", "kosher", "low-carb"}
VALID_CUISINES = {"italian", "indian", "japanese", "mexican", "thai", "mediterranean", "chinese", "american", "french", "korean"}
VALID_SKILLS   = {"beginner", "intermediate", "advanced"}


@csrf_protect
@require_http_methods(["POST"])
@login_required
def save_preferences(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    user     = request.user
    dietary  = [d for d in data.get("dietary_restrictions", []) if d in VALID_DIETARY]
    cuisines = [c for c in data.get("cuisine_preferences",  []) if c in VALID_CUISINES]
    skill    = data.get("cooking_skill", "intermediate")
    servings = int(data.get("default_servings", 2))

    if skill not in VALID_SKILLS:
        skill = "intermediate"
    servings = max(1, min(servings, 20))

    user.dietary_restrictions = dietary
    user.cuisine_preferences  = cuisines
    user.cooking_skill        = skill
    user.default_servings     = servings
    user.save(update_fields=["dietary_restrictions", "cuisine_preferences", "cooking_skill", "default_servings"])

    return JsonResponse({"ok": True})


@login_required
@require_http_methods(["GET"])
def list_notifications(request):
    notifications = Notification.objects.filter(user=request.user).order_by("-created_at")[:20]
    unread_count  = Notification.objects.filter(user=request.user, is_read=False).count()
    data = [
        {
            "id":         n.id,
            "type":       n.type,
            "title":      n.title,
            "body":       n.body,
            "link":       n.link,
            "is_read":    n.is_read,
            "created_at": n.created_at.isoformat(),
        }
        for n in notifications
    ]
    return JsonResponse({"notifications": data, "unread_count": unread_count})


@login_required
@csrf_protect
@require_http_methods(["POST"])
def mark_notification_read(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    notif_id = data.get("id")
    if notif_id:
        Notification.objects.filter(id=notif_id, user=request.user).update(is_read=True)
    return JsonResponse({"ok": True})


@login_required
@csrf_protect
@require_http_methods(["POST"])
def mark_all_notifications_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return JsonResponse({"ok": True})
