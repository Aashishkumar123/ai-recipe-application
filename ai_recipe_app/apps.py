import sys
from pathlib import Path
from django.apps import AppConfig


class AiRecipeAppConfig(AppConfig):
    name = 'ai_recipe_app'

    def ready(self):
        from loguru import logger
        from django.conf import settings

        # Remove Loguru's default stderr handler so we can replace it
        logger.remove()

        # ── Console sink ──────────────────────────────────────────────────────
        logger.add(
            sys.stderr,
            level="DEBUG",
            colorize=True,
            format=(
                "<green>{time:HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> "
                "— <level>{message}</level>"
            ),
        )

        # ── Rotating file sink ────────────────────────────────────────────────
        log_dir = Path(settings.BASE_DIR) / "logs"
        log_dir.mkdir(exist_ok=True)
        logger.add(
            log_dir / "recipe_chef_{time:YYYY-MM-DD}.log",
            level="DEBUG",
            rotation="00:00",       # new file every midnight
            retention="30 days",
            encoding="utf-8",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} — {message}",
        )

        logger.info("Recipe Chef — app ready, logging initialised")
