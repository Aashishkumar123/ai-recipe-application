VALID_LANGUAGES = ("English", "Hindi", "Spanish", "French", "Japanese")

def theme(request):
    return {
        "theme": request.session.get("theme", "light"),
        "language": request.session.get("language", "English"),
    }
