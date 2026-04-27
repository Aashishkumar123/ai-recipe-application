# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
uv sync

# Run development server
uv run python manage.py runserver

# Apply migrations
uv run python manage.py migrate

# Open Django shell
uv run python manage.py shell

# Lint
uv run ruff check .
uv run ruff format .
```

## Tailwind CSS

Tailwind uses the standalone CLI binary (`./tailwindcss`) — no Node.js required.

```bash
# One-off build (minified) — always use this path
./tailwindcss -i static/src/input.css -o static/output.css --minify

# Watch mode during development
./tailwindcss -i static/src/input.css -o static/output.css --watch
```

- Source: `static/src/input.css` (plain CSS + `@apply` directives + `@source` directives scanning `templates/` and `static/*.js`)
- Output: `static/output.css` — this is the file Django actually serves (`STATICFILES_DIRS = [BASE_DIR / 'static']`)
- **Always rebuild after editing `input.css`**; the compiled file is committed
- The `tailwindcss` binary is gitignored — re-download for macOS arm64 from the latest GitHub release

## Environment

Requires a `.env` file at the project root:

```
MISTRAL_API_KEY=<your_key>
MISTRAL_MODEL=mistral-large-latest
```

`config/settings.py` raises `KeyError` at startup if either is missing.

Email defaults to the Django console backend (OTP codes print to terminal). For real email, add to `.env`:

```
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=...
EMAIL_HOST_USER=...
EMAIL_HOST_PASSWORD=...
DEFAULT_FROM_EMAIL=...
```

## Architecture

### Two Django apps

**`ai_recipe_app`** — recipe chat feature  
**`authentication`** — custom user model, email OTP login, settings, avatar upload

### URL structure

```
/               → home page (inline view in config/urls.py)
/chat/          → chat interface (ai_recipe_app.urls)
/chat/<uuid>/   → load a specific chat from history
/auth/          → authentication (authentication.urls)
```

All chat API endpoints live under `/chat/api/`:
- `POST api/message/` — streams SSE tokens for a recipe
- `POST api/save-bot-message/` — persists rendered bot HTML after streaming
- `POST api/rename-chat/` — renames a chat
- `POST api/delete-chat/` — deletes a chat and its messages

Auth API endpoints live under `/auth/`:
- `POST request-otp/`, `POST verify-otp/`, `POST logout/`
- `POST upload-avatar/`, `POST api/set-theme/`, `POST api/set-language/`

### Authentication

Custom `authentication.User` model uses email as the unique identifier (no username). Login is passwordless — a 6-digit OTP is emailed and verified via `EmailOTPBackend`. OTP records live in `authentication.EmailOTP` (5-minute TTL). Email sending is wrapped in a Django background task (`@task` decorator using `ImmediateBackend` in dev).

### Recipe streaming flow

1. User submits a dish → `POST /chat/api/message/` → `views.chat_message`
2. View resolves/creates a `Chat` row, fetches the last 10 `ChatMessage` rows as LangChain history, then saves the user's message
3. `stream_recipe(dish_name, language, history)` in `ai_recipe_app/chat.py` builds a message list: `[SystemMessage, *history, HumanMessage]` and streams through `ChatMistralAI | StrOutputParser`
4. Tokens are yielded as SSE: `data: {"token": "..."}` followed by a final `data: {"done": true, "chat_id": "...", "chat_title": "..."}`
5. Frontend (`static/chat.js`) accumulates tokens, renders with `marked.parse()`, then on `done`: runs `applyRecipeStyles()`, pushes URL via `history.pushState`, updates the sidebar, and saves the rendered HTML via `api/save-bot-message/`

### Bot message HTML storage

Bot messages are stored as **rendered HTML** (output of `marked.parse()` + `applyRecipeStyles()`). When chat history loads, `{{ msg.content|safe }}` renders it identically to the live streaming view. `html_to_text()` in `ai_recipe_app/utils.py` strips HTML before passing bot content back to the LLM as `AIMessage` history.

### Context processor

`context_processors.context_processors` (registered in `settings.py`) runs on every request. For authenticated users it queries all `Chat` rows and buckets them into `chats_today / chats_yesterday / chats_week / chats_older` — these drive the sidebar history without any extra view code.

### Session-stored preferences

`language` (default: `"English"`) and `theme` (`"light"`, `"dark"`, `"system"`) are stored in the Django session and injected into every template via the context processor. The LLM uses `language` to respond in the user's chosen language.

### Static and template layout

All templates are in the root `templates/` directory (not inside apps). All static assets (`chat.js`, `sidebar.js`, `output.css`, `static/src/input.css`) are in the root `static/` directory. The app-level `ai_recipe_app/static/` directory exists but is **not served** — do not write output files there.

### Frontend JS split

- `static/sidebar.js` — loaded on every page via `base.html`; handles sidebar toggle/collapse, profile dropdown, sign-in modal, language selection, and the 3-dot chat context menu (rename/delete)
- `static/chat.js` — loaded only on the chat page; handles message submission, SSE streaming, markdown rendering, copy buttons, and sidebar updates for new chats

### Loguru logging

Configured once in `ai_recipe_app/apps.py` `AppConfig.ready()`. Adds a colorized stderr sink and a rotating daily file sink at `logs/recipe_chef_YYYY-MM-DD.log` (30-day retention). Use `from loguru import logger` anywhere — no per-module configuration needed.
