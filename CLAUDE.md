# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

This project uses `uv` for dependency management and Django for the web server.

```bash
# Install dependencies
uv sync

# Run development server
uv run python manage.py runserver

# Apply migrations
uv run python manage.py migrate

# Open Django shell
uv run python manage.py shell
```

## Environment

Requires a `.env` file at the project root with:

```
MISTRAL_API_KEY=<your_key>
MISTRAL_MODEL=mistral-large-latest
```

Both variables are required at startup — `config/settings.py` will raise `KeyError` if either is missing.

## Architecture

The app is a single-page Django app with a streaming chat interface for recipe generation.

**Request flow:**
1. User submits a dish name via the frontend (`chat.js`)
2. `POST /api/message/` hits `views.chat_message` in `ai_recipe_app/views.py`
3. The view calls `stream_recipe(dish_name)` from `ai_recipe_app/chat.py`
4. `chat.py` builds a LangChain chain: `RECIPE_PROMPT | ChatMistralAI | StrOutputParser` and streams tokens
5. Tokens are returned as Server-Sent Events (SSE) in `data: {"token": "..."}` format
6. The frontend appends tokens to the UI and renders the final output as Markdown

**Key files:**
- `ai_recipe_app/chat.py` — LangChain chain setup; the `LLM` and `recipe_chain` are module-level singletons initialized at import time
- `ai_recipe_app/prompt.py` — `RECIPE_SYSTEM_PROMPT` defines the strict recipe-only persona and Markdown output format
- `ai_recipe_app/views.py` — SSE streaming via `StreamingHttpResponse`
- `config/settings.py` — reads `MISTRAL_API_KEY` and `MISTRAL_MODEL` from environment

**Frontend:** `chat.js` and `chat.css` live in `ai_recipe_app/static/`. The UI uses the browser's native `EventSource`-style fetch with streaming to receive and render SSE tokens as Markdown.
