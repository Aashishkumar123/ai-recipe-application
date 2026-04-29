import os
import sys

# Put the project root on sys.path so Django packages are importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

# Run pending migrations automatically on Vercel cold start.
# migrate is a no-op when all migrations are already applied, so this is safe.
if os.environ.get("VERCEL"):
    from django.core.management import call_command
    call_command("migrate", "--no-input", verbosity=0)

from django.core.wsgi import get_wsgi_application
app = get_wsgi_application()
