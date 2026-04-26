import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required

from context_processors import VALID_LANGUAGES
from .models import EmailOTP
from .utils import email_users
from django.shortcuts import render

User = get_user_model()


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

    login(request, user)
    return JsonResponse({"ok": True, "name": user.get_full_name(), "email": user.email})


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
