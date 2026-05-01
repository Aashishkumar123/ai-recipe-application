import json
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from authentication.models import Notification, User
from .models import Chat, ChatMessage, StepDetail
from .utils import html_to_text


# ── Model tests ───────────────────────────────────────────────────────────────

class ChatModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="chatmodel@example.com")

    def test_create_chat_defaults(self):
        chat = Chat.objects.create(title="Pasta", user=self.user)
        self.assertEqual(chat.title, "Pasta")
        self.assertFalse(chat.is_public)
        self.assertFalse(chat.is_pinned)
        self.assertIsInstance(chat.id, uuid.UUID)

    def test_str_returns_title(self):
        chat = Chat.objects.create(title="Biryani", user=self.user)
        self.assertEqual(str(chat), "Biryani")

    def test_cascade_delete_removes_messages(self):
        chat = Chat.objects.create(title="Test", user=self.user)
        ChatMessage.objects.create(chat=chat, sender="user", content="Hello")
        chat.delete()
        self.assertEqual(ChatMessage.objects.count(), 0)


class ChatMessageModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="msgmodel@example.com")
        self.chat = Chat.objects.create(title="Test", user=self.user)

    def test_create_user_message(self):
        msg = ChatMessage.objects.create(chat=self.chat, sender="user", content="Hello")
        self.assertEqual(msg.sender, "user")
        self.assertEqual(msg.content, "Hello")

    def test_create_bot_message(self):
        msg = ChatMessage.objects.create(chat=self.chat, sender="bot", content="<h1>Recipe</h1>")
        self.assertEqual(msg.sender, "bot")

    def test_str_contains_sender(self):
        msg = ChatMessage.objects.create(chat=self.chat, sender="user", content="Hi")
        self.assertIn("user", str(msg))


class StepDetailModelTests(TestCase):
    def test_make_key_is_deterministic(self):
        key1 = StepDetail.make_key("Pasta Carbonara", "Boil the pasta")
        key2 = StepDetail.make_key("Pasta Carbonara", "Boil the pasta")
        self.assertEqual(key1, key2)

    def test_make_key_is_case_insensitive(self):
        key1 = StepDetail.make_key("Pasta", "Boil")
        key2 = StepDetail.make_key("pasta", "boil")
        self.assertEqual(key1, key2)

    def test_make_key_length_is_64(self):
        key = StepDetail.make_key("recipe", "step")
        self.assertEqual(len(key), 64)

    def test_make_key_differs_for_different_inputs(self):
        self.assertNotEqual(
            StepDetail.make_key("Pasta", "Boil"),
            StepDetail.make_key("Pasta", "Fry"),
        )

    def test_str_contains_stepdetail(self):
        sd = StepDetail.objects.create(
            key=StepDetail.make_key("recipe", "step"),
            step_text="step",
            detail="explanation",
        )
        self.assertIn("StepDetail", str(sd))


# ── Utils ─────────────────────────────────────────────────────────────────────

class HtmlToTextTests(TestCase):
    def test_strips_tags(self):
        result = html_to_text("<h1>Hello</h1><p>World</p>")
        self.assertIn("Hello", result)
        self.assertIn("World", result)
        self.assertNotIn("<h1>", result)
        self.assertNotIn("<p>", result)

    def test_decodes_html_entities(self):
        result = html_to_text("&amp; &lt; &gt;")
        self.assertEqual(result, "& < >")

    def test_empty_string_returns_empty(self):
        self.assertEqual(html_to_text(""), "")

    def test_plain_text_unchanged(self):
        self.assertEqual(html_to_text("Hello world"), "Hello world")

    def test_nested_tags_stripped(self):
        result = html_to_text("<ul><li>item</li></ul>")
        self.assertIn("item", result)
        self.assertNotIn("<li>", result)

    def test_strips_leading_trailing_whitespace(self):
        result = html_to_text("  <p>  text  </p>  ")
        self.assertEqual(result.strip(), result)


# ── chat module ───────────────────────────────────────────────────────────────

class BuildSystemPromptTests(TestCase):
    def test_anonymous_user_returns_base_prompt(self):
        from ai_recipe_app.chat import _build_system_prompt
        prompt = _build_system_prompt("English", user=None)
        self.assertIn("RecipeChef", prompt)
        self.assertIn("English", prompt)

    def test_unauthenticated_user_returns_base_prompt(self):
        from django.contrib.auth.models import AnonymousUser
        from ai_recipe_app.chat import _build_system_prompt
        prompt = _build_system_prompt("Spanish", user=AnonymousUser())
        self.assertIn("Spanish", prompt)
        self.assertNotIn("User Profile", prompt)

    def test_authenticated_user_with_prefs_adds_profile_block(self):
        from ai_recipe_app.chat import _build_system_prompt
        user = User(
            email="prompt@example.com",
            cooking_skill="advanced",
            default_servings=4,
            dietary_restrictions=["vegan"],
            cuisine_preferences=["italian"],
        )
        prompt = _build_system_prompt("English", user=user)
        self.assertIn("Advanced", prompt)
        self.assertIn("Vegan", prompt)
        self.assertIn("Italian", prompt)
        self.assertIn("4", prompt)

    def test_authenticated_user_no_prefs_returns_base_prompt(self):
        from ai_recipe_app.chat import _build_system_prompt
        user = User(email="noprof@example.com", cooking_skill="", default_servings=0)
        prompt = _build_system_prompt("English", user=user)
        self.assertNotIn("User Profile", prompt)


# ── context_processors ────────────────────────────────────────────────────────

class ContextProcessorTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(email="ctx@example.com")

    def test_anonymous_user_gets_defaults(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.context["theme"], "light")
        self.assertEqual(response.context["name"], "Guest")
        self.assertEqual(response.context["chats_pinned"], [])
        self.assertEqual(response.context["chats_today"], [])
        self.assertEqual(response.context["unread_notifications_count"], 0)

    def test_today_chat_is_bucketed_correctly(self):
        self.client.force_login(self.user)
        Chat.objects.create(title="Today Chat", user=self.user)
        response = self.client.get(reverse("chat"))
        self.assertEqual(len(response.context["chats_today"]), 1)
        self.assertEqual(len(response.context["chats_yesterday"]), 0)

    def test_yesterday_chat_is_bucketed_correctly(self):
        self.client.force_login(self.user)
        chat = Chat.objects.create(title="Yesterday Chat", user=self.user)
        Chat.objects.filter(id=chat.id).update(
            created_at=timezone.now() - timedelta(hours=30)
        )
        response = self.client.get(reverse("chat"))
        self.assertEqual(len(response.context["chats_yesterday"]), 1)
        self.assertEqual(len(response.context["chats_today"]), 0)

    def test_older_chat_is_bucketed_correctly(self):
        self.client.force_login(self.user)
        chat = Chat.objects.create(title="Old Chat", user=self.user)
        Chat.objects.filter(id=chat.id).update(
            created_at=timezone.now() - timedelta(days=10)
        )
        response = self.client.get(reverse("chat"))
        self.assertEqual(len(response.context["chats_older"]), 1)

    def test_pinned_chats_are_separate(self):
        self.client.force_login(self.user)
        Chat.objects.create(title="Pinned", user=self.user, is_pinned=True)
        Chat.objects.create(title="Regular", user=self.user)
        response = self.client.get(reverse("chat"))
        self.assertEqual(len(response.context["chats_pinned"]), 1)
        self.assertEqual(len(response.context["chats_today"]), 1)

    def test_pinned_chat_not_in_today_bucket(self):
        self.client.force_login(self.user)
        Chat.objects.create(title="Pinned", user=self.user, is_pinned=True)
        response = self.client.get(reverse("chat"))
        self.assertEqual(len(response.context["chats_pinned"]), 1)
        self.assertEqual(len(response.context["chats_today"]), 0)

    def test_unread_notification_count(self):
        self.client.force_login(self.user)
        Notification.objects.create(user=self.user, type="system", title="Test")
        response = self.client.get(reverse("chat"))
        self.assertEqual(response.context["unread_notifications_count"], 1)

    def test_theme_from_session(self):
        session = self.client.session
        session["theme"] = "dark"
        session.save()
        response = self.client.get(reverse("home"))
        self.assertEqual(response.context["theme"], "dark")


# ── chat view ─────────────────────────────────────────────────────────────────

class ChatViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(email="chatview@example.com")

    def test_anonymous_user_sees_chat_page(self):
        response = self.client.get(reverse("chat"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "chat.html")

    def test_authenticated_user_sees_chat_page(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("chat"))
        self.assertEqual(response.status_code, 200)

    def test_load_own_chat_history(self):
        self.client.force_login(self.user)
        chat = Chat.objects.create(title="My Recipe", user=self.user)
        ChatMessage.objects.create(chat=chat, sender="user", content="Make pasta")
        response = self.client.get(reverse("chat-history", args=[chat.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["chat_obj"], chat)
        self.assertEqual(len(response.context["chat_history"]), 1)

    def test_nonexistent_chat_renders_404_template(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("chat-history", args=[uuid.uuid4()]))
        self.assertTemplateUsed(response, "404.html")

    def test_other_users_chat_renders_404_template(self):
        other = User.objects.create_user(email="other@example.com")
        chat = Chat.objects.create(title="Other", user=other)
        self.client.force_login(self.user)
        response = self.client.get(reverse("chat-history", args=[chat.id]))
        self.assertTemplateUsed(response, "404.html")


# ── public_chat view ──────────────────────────────────────────────────────────

class PublicChatViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user(email="owner@example.com")
        self.viewer = User.objects.create_user(email="viewer@example.com")
        self.public_chat = Chat.objects.create(
            title="Public Recipe", user=self.owner, is_public=True
        )
        self.private_chat = Chat.objects.create(
            title="Private", user=self.owner, is_public=False
        )
        ChatMessage.objects.create(chat=self.public_chat, sender="user", content="Hello")
        ChatMessage.objects.create(chat=self.public_chat, sender="bot", content="<p>Recipe</p>")

    def test_public_chat_accessible_anonymously(self):
        response = self.client.get(reverse("public-chat", args=[self.public_chat.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "shared_chat.html")

    def test_private_chat_returns_404(self):
        response = self.client.get(reverse("public-chat", args=[self.private_chat.id]))
        self.assertEqual(response.status_code, 404)

    def test_nonexistent_chat_returns_404(self):
        response = self.client.get(reverse("public-chat", args=[uuid.uuid4()]))
        self.assertEqual(response.status_code, 404)

    def test_authenticated_viewer_creates_notification_for_owner(self):
        self.client.force_login(self.viewer)
        self.client.get(reverse("public-chat", args=[self.public_chat.id]))
        self.assertTrue(
            Notification.objects.filter(
                user=self.owner, type="shared_chat_viewed"
            ).exists()
        )

    def test_owner_viewing_own_chat_creates_no_notification(self):
        self.client.force_login(self.owner)
        self.client.get(reverse("public-chat", args=[self.public_chat.id]))
        self.assertFalse(
            Notification.objects.filter(
                user=self.owner, type="shared_chat_viewed"
            ).exists()
        )

    def test_notification_created_only_once_for_same_viewer(self):
        self.client.force_login(self.viewer)
        self.client.get(reverse("public-chat", args=[self.public_chat.id]))
        self.client.get(reverse("public-chat", args=[self.public_chat.id]))
        count = Notification.objects.filter(
            user=self.owner, type="shared_chat_viewed"
        ).count()
        self.assertEqual(count, 1)

    def test_anonymous_viewer_creates_no_notification(self):
        self.client.get(reverse("public-chat", args=[self.public_chat.id]))
        self.assertFalse(
            Notification.objects.filter(user=self.owner, type="shared_chat_viewed").exists()
        )


# ── chat_message (SSE streaming) ──────────────────────────────────────────────

class ChatMessageViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(email="stream@example.com")

    def _post(self, data):
        return self.client.post(
            reverse("message"),
            data=json.dumps(data),
            content_type="application/json",
        )

    def _consume(self, response):
        return b"".join(response.streaming_content).decode()

    def test_empty_message_returns_400(self):
        response = self._post({"message": ""})
        self.assertEqual(response.status_code, 400)

    def test_whitespace_only_message_returns_400(self):
        response = self._post({"message": "   "})
        self.assertEqual(response.status_code, 400)

    def test_invalid_json_returns_400(self):
        response = self.client.post(
            reverse("message"), data="not json", content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

    def test_get_not_allowed(self):
        response = self.client.get(reverse("message"))
        self.assertEqual(response.status_code, 405)

    @patch("ai_recipe_app.views.stream_recipe", return_value=iter(["Hello", " world"]))
    def test_anonymous_user_gets_sse_stream(self, _):
        response = self._post({"message": "pizza"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response["Content-Type"])
        content = self._consume(response)
        self.assertIn('"done": true', content)
        self.assertIn('"token": "Hello"', content)

    @patch("ai_recipe_app.views.stream_recipe", return_value=iter(["Hello", " world"]))
    def test_anonymous_user_no_chat_id_in_done_payload(self, _):
        content = self._consume(self._post({"message": "pizza"}))
        # Anonymous user has no chat_obj, so done payload has no chat_id
        done_event = [
            line for line in content.split("\n\n") if '"done": true' in line
        ]
        self.assertEqual(len(done_event), 1)
        done_data = json.loads(done_event[0].replace("data: ", ""))
        self.assertNotIn("chat_id", done_data)

    @patch("ai_recipe_app.views.stream_recipe", return_value=iter(["Pasta", " is great"]))
    def test_authenticated_user_creates_new_chat(self, _):
        self.client.force_login(self.user)
        self.assertEqual(Chat.objects.filter(user=self.user).count(), 0)
        self._consume(self._post({"message": "make me pasta"}))
        self.assertEqual(Chat.objects.filter(user=self.user).count(), 1)
        chat = Chat.objects.get(user=self.user)
        self.assertEqual(chat.title, "make me pasta")
        self.assertTrue(ChatMessage.objects.filter(chat=chat, sender="user").exists())

    @patch("ai_recipe_app.views.stream_recipe", return_value=iter(["token"]))
    def test_authenticated_user_chat_id_emitted_first(self, _):
        self.client.force_login(self.user)
        content = self._consume(self._post({"message": "pizza"}))
        events = [e for e in content.split("\n\n") if e.strip()]
        first = json.loads(events[0].replace("data: ", ""))
        self.assertIn("chat_id", first)

    @patch("ai_recipe_app.views.stream_recipe", return_value=iter(["Hi"]))
    def test_authenticated_user_resumes_existing_chat(self, _):
        self.client.force_login(self.user)
        chat = Chat.objects.create(title="Old Chat", user=self.user)
        self._consume(self._post({"message": "follow up", "chat_id": str(chat.id)}))
        self.assertEqual(Chat.objects.filter(user=self.user).count(), 1)

    @patch("ai_recipe_app.views.stream_recipe", return_value=iter(["token"]))
    def test_unknown_chat_id_creates_new_chat(self, _):
        self.client.force_login(self.user)
        self._consume(self._post({"message": "pasta", "chat_id": str(uuid.uuid4())}))
        self.assertEqual(Chat.objects.filter(user=self.user).count(), 1)

    @patch("ai_recipe_app.views.stream_recipe", return_value=iter(["token"]))
    def test_stream_uses_session_language(self, mock_stream):
        session = self.client.session
        session["language"] = "French"
        session.save()
        self._consume(self._post({"message": "crepes"}))
        _, kwargs = mock_stream.call_args
        self.assertEqual(kwargs.get("language") or mock_stream.call_args[0][1], "French")


# ── save_bot_message ──────────────────────────────────────────────────────────

class SaveBotMessageViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(email="botmsg@example.com")
        self.chat = Chat.objects.create(title="Test", user=self.user)

    def _post(self, data):
        return self.client.post(
            reverse("save_bot_message"),
            data=json.dumps(data),
            content_type="application/json",
        )

    def test_unauthenticated_returns_401(self):
        response = self._post({"chat_id": str(self.chat.id), "content": "<h1>R</h1>"})
        self.assertEqual(response.status_code, 401)

    def test_valid_save_creates_bot_message(self):
        self.client.force_login(self.user)
        response = self._post({"chat_id": str(self.chat.id), "content": "<h1>Recipe</h1>"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertTrue(ChatMessage.objects.filter(chat=self.chat, sender="bot").exists())

    def test_missing_content_returns_400(self):
        self.client.force_login(self.user)
        response = self._post({"chat_id": str(self.chat.id)})
        self.assertEqual(response.status_code, 400)

    def test_missing_chat_id_returns_400(self):
        self.client.force_login(self.user)
        response = self._post({"content": "<h1>R</h1>"})
        self.assertEqual(response.status_code, 400)

    def test_wrong_chat_id_returns_404(self):
        self.client.force_login(self.user)
        response = self._post({"chat_id": str(uuid.uuid4()), "content": "<p>Hi</p>"})
        self.assertEqual(response.status_code, 404)

    def test_other_users_chat_returns_404(self):
        other = User.objects.create_user(email="other@example.com")
        other_chat = Chat.objects.create(title="Other", user=other)
        self.client.force_login(self.user)
        response = self._post({"chat_id": str(other_chat.id), "content": "<p>Hi</p>"})
        self.assertEqual(response.status_code, 404)

    def test_invalid_json_returns_400(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("save_bot_message"), data="not json", content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)


# ── rename_chat ───────────────────────────────────────────────────────────────

class RenameChatViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(email="rename@example.com")
        self.chat = Chat.objects.create(title="Old Title", user=self.user)

    def _post(self, data):
        return self.client.post(
            reverse("rename_chat"),
            data=json.dumps(data),
            content_type="application/json",
        )

    def test_rename_success(self):
        self.client.force_login(self.user)
        response = self._post({"chat_id": str(self.chat.id), "title": "New Title"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.chat.refresh_from_db()
        self.assertEqual(self.chat.title, "New Title")

    def test_title_truncated_to_255(self):
        self.client.force_login(self.user)
        self._post({"chat_id": str(self.chat.id), "title": "A" * 300})
        self.chat.refresh_from_db()
        self.assertEqual(len(self.chat.title), 255)

    def test_unauthenticated_returns_401(self):
        response = self._post({"chat_id": str(self.chat.id), "title": "New"})
        self.assertEqual(response.status_code, 401)

    def test_chat_not_found_returns_404(self):
        self.client.force_login(self.user)
        response = self._post({"chat_id": str(uuid.uuid4()), "title": "New"})
        self.assertEqual(response.status_code, 404)

    def test_missing_title_returns_400(self):
        self.client.force_login(self.user)
        response = self._post({"chat_id": str(self.chat.id), "title": ""})
        self.assertEqual(response.status_code, 400)

    def test_other_users_chat_returns_404(self):
        other = User.objects.create_user(email="other2@example.com")
        other_chat = Chat.objects.create(title="Other", user=other)
        self.client.force_login(self.user)
        response = self._post({"chat_id": str(other_chat.id), "title": "Stolen"})
        self.assertEqual(response.status_code, 404)


# ── delete_chat ───────────────────────────────────────────────────────────────

class DeleteChatViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(email="delete@example.com")
        self.chat = Chat.objects.create(title="To Delete", user=self.user)

    def _post(self, data):
        return self.client.post(
            reverse("delete_chat"),
            data=json.dumps(data),
            content_type="application/json",
        )

    def test_delete_success(self):
        self.client.force_login(self.user)
        response = self._post({"chat_id": str(self.chat.id)})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertFalse(Chat.objects.filter(id=self.chat.id).exists())

    def test_unauthenticated_returns_401(self):
        response = self._post({"chat_id": str(self.chat.id)})
        self.assertEqual(response.status_code, 401)

    def test_other_users_chat_not_deleted(self):
        other = User.objects.create_user(email="other3@example.com")
        self.client.force_login(other)
        response = self._post({"chat_id": str(self.chat.id)})
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Chat.objects.filter(id=self.chat.id).exists())

    def test_missing_chat_id_returns_400(self):
        self.client.force_login(self.user)
        response = self._post({})
        self.assertEqual(response.status_code, 400)


# ── pin_chat ──────────────────────────────────────────────────────────────────

class PinChatViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(email="pin@example.com")

    def _post(self, chat_id):
        return self.client.post(
            reverse("pin_chat"),
            data=json.dumps({"chat_id": str(chat_id)}),
            content_type="application/json",
        )

    def test_pin_unpinned_chat(self):
        chat = Chat.objects.create(title="Pin Me", user=self.user)
        self.client.force_login(self.user)
        response = self._post(chat.id)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["pinned"])
        chat.refresh_from_db()
        self.assertTrue(chat.is_pinned)

    def test_unpin_pinned_chat(self):
        chat = Chat.objects.create(title="Unpin Me", user=self.user, is_pinned=True)
        self.client.force_login(self.user)
        response = self._post(chat.id)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["pinned"])
        chat.refresh_from_db()
        self.assertFalse(chat.is_pinned)

    def test_pin_limit_of_5_enforced(self):
        for i in range(5):
            Chat.objects.create(title=f"Pinned {i}", user=self.user, is_pinned=True)
        sixth = Chat.objects.create(title="Sixth", user=self.user)
        self.client.force_login(self.user)
        response = self._post(sixth.id)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "limit")
        sixth.refresh_from_db()
        self.assertFalse(sixth.is_pinned)

    def test_unpinning_when_at_limit_succeeds(self):
        pinned = [
            Chat.objects.create(title=f"P{i}", user=self.user, is_pinned=True)
            for i in range(5)
        ]
        self.client.force_login(self.user)
        response = self._post(pinned[0].id)  # unpin one
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["pinned"])

    def test_unauthenticated_returns_401(self):
        chat = Chat.objects.create(title="Test", user=self.user)
        response = self._post(chat.id)
        self.assertEqual(response.status_code, 401)

    def test_other_users_chat_returns_404(self):
        other = User.objects.create_user(email="other4@example.com")
        chat = Chat.objects.create(title="Other", user=other)
        self.client.force_login(self.user)
        response = self._post(chat.id)
        self.assertEqual(response.status_code, 404)


# ── share_chat ────────────────────────────────────────────────────────────────

class ShareChatViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(email="share@example.com")
        self.chat = Chat.objects.create(title="Share Me", user=self.user)

    def _post(self, data):
        return self.client.post(
            reverse("share_chat"),
            data=json.dumps(data),
            content_type="application/json",
        )

    def test_make_public_returns_url(self):
        self.client.force_login(self.user)
        response = self._post({"chat_id": str(self.chat.id), "public": True})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["is_public"])
        self.assertIn("/chat/public/", data["public_url"])
        self.chat.refresh_from_db()
        self.assertTrue(self.chat.is_public)

    def test_make_private_returns_null_url(self):
        self.chat.is_public = True
        self.chat.save()
        self.client.force_login(self.user)
        response = self._post({"chat_id": str(self.chat.id), "public": False})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data["is_public"])
        self.assertIsNone(data["public_url"])

    def test_unauthenticated_returns_401(self):
        response = self._post({"chat_id": str(self.chat.id), "public": True})
        self.assertEqual(response.status_code, 401)

    def test_missing_public_field_returns_400(self):
        self.client.force_login(self.user)
        response = self._post({"chat_id": str(self.chat.id)})
        self.assertEqual(response.status_code, 400)

    def test_missing_chat_id_returns_400(self):
        self.client.force_login(self.user)
        response = self._post({"public": True})
        self.assertEqual(response.status_code, 400)

    def test_other_users_chat_returns_404(self):
        other = User.objects.create_user(email="other5@example.com")
        other_chat = Chat.objects.create(title="Other", user=other)
        self.client.force_login(self.user)
        response = self._post({"chat_id": str(other_chat.id), "public": True})
        self.assertEqual(response.status_code, 404)


# ── step_detail ───────────────────────────────────────────────────────────────

class StepDetailViewTests(TestCase):
    def setUp(self):
        self.client = Client()

    def _post(self, data):
        return self.client.post(
            reverse("step_detail"),
            data=json.dumps(data),
            content_type="application/json",
        )

    def test_missing_step_returns_400(self):
        response = self._post({"recipe": "Pasta", "step": ""})
        self.assertEqual(response.status_code, 400)

    def test_no_step_key_returns_400(self):
        response = self._post({"recipe": "Pasta"})
        self.assertEqual(response.status_code, 400)

    def test_invalid_json_returns_400(self):
        response = self.client.post(
            reverse("step_detail"), data="bad json", content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

    def test_cache_hit_returns_cached_detail(self):
        key = StepDetail.make_key("Pasta", "Boil the pasta until al dente")
        StepDetail.objects.create(key=key, step_text="Boil...", detail="Great tip!")
        response = self._post({"recipe": "Pasta", "step": "Boil the pasta until al dente"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["detail"], "Great tip!")
        self.assertTrue(data["cached"])

    @patch("ai_recipe_app.chat.llm")
    def test_fresh_generation_calls_llm_and_caches(self, mock_llm):
        mock_llm.__or__.return_value.invoke.return_value = "Explanation from LLM"
        response = self._post({"recipe": "Pasta", "step": "Stir continuously for 2 minutes"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["detail"], "Explanation from LLM")
        self.assertFalse(data["cached"])
        self.assertTrue(
            StepDetail.objects.filter(
                key=StepDetail.make_key("Pasta", "Stir continuously for 2 minutes")
            ).exists()
        )

    @patch("ai_recipe_app.chat.llm")
    def test_no_recipe_context_still_works(self, mock_llm):
        mock_llm.__or__.return_value.invoke.return_value = "Generic tip"
        response = self._post({"step": "Season to taste"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["detail"], "Generic tip")

    @patch("ai_recipe_app.chat.llm")
    def test_llm_error_returns_500(self, mock_llm):
        mock_llm.__or__.return_value.invoke.side_effect = Exception("LLM unavailable")
        response = self._post({"recipe": "Pasta", "step": "Some step that fails"})
        self.assertEqual(response.status_code, 500)
        self.assertIn("error", response.json())

    def test_get_not_allowed(self):
        response = self.client.get(reverse("step_detail"))
        self.assertEqual(response.status_code, 405)


# ── youtube_videos ────────────────────────────────────────────────────────────

class YouTubeVideosViewTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_empty_query_returns_empty_list(self):
        response = self.client.get(reverse("youtube_videos"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["videos"], [])

    def test_whitespace_query_returns_empty(self):
        response = self.client.get(reverse("youtube_videos"), {"q": "   "})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["videos"], [])

    @patch("scrapetube.get_search")
    def test_valid_query_returns_video_list(self, mock_search):
        mock_search.return_value = [
            {
                "videoId": "abc123",
                "title": {"runs": [{"text": "Amazing Pasta Recipe"}]},
                "longBylineText": {"runs": [{"text": "Chef Channel"}]},
            }
        ]
        response = self.client.get(reverse("youtube_videos"), {"q": "pasta"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["videos"]), 1)
        v = data["videos"][0]
        self.assertEqual(v["id"], "abc123")
        self.assertEqual(v["title"], "Amazing Pasta Recipe")
        self.assertEqual(v["channel"], "Chef Channel")
        self.assertIn("abc123", v["thumbnail"])
        self.assertIn("mqdefault.jpg", v["thumbnail"])
        mock_search.assert_called_once_with("pasta recipe", limit=3)

    @patch("scrapetube.get_search")
    def test_video_without_id_is_skipped(self, mock_search):
        mock_search.return_value = [{"title": {"runs": [{"text": "No ID"}]}}]
        response = self.client.get(reverse("youtube_videos"), {"q": "pasta"})
        self.assertEqual(response.json()["videos"], [])

    @patch("scrapetube.get_search")
    def test_scrapetube_exception_returns_empty(self, mock_search):
        mock_search.side_effect = Exception("Network error")
        response = self.client.get(reverse("youtube_videos"), {"q": "pasta"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["videos"], [])

    @patch("scrapetube.get_search")
    def test_uses_short_byline_fallback(self, mock_search):
        mock_search.return_value = [
            {
                "videoId": "xyz",
                "title": {"runs": [{"text": "Test"}]},
                "shortBylineText": {"runs": [{"text": "Short Channel"}]},
            }
        ]
        response = self.client.get(reverse("youtube_videos"), {"q": "curry"})
        self.assertEqual(response.json()["videos"][0]["channel"], "Short Channel")

    def test_post_not_allowed(self):
        response = self.client.post(reverse("youtube_videos"))
        self.assertEqual(response.status_code, 405)


# ── download_pdf ──────────────────────────────────────────────────────────────

class DownloadPDFViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(email="pdf@example.com")

    def _post(self, data):
        return self.client.post(
            reverse("download_pdf"),
            data=json.dumps(data),
            content_type="application/json",
        )

    def test_unauthenticated_returns_401(self):
        response = self._post({"html": "<h1>Recipe</h1>", "title": "Pasta"})
        self.assertEqual(response.status_code, 401)

    def test_empty_html_returns_400(self):
        self.client.force_login(self.user)
        response = self._post({"html": "", "title": "Recipe"})
        self.assertEqual(response.status_code, 400)

    def test_invalid_json_returns_400(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("download_pdf"), data="not json", content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

    def test_valid_html_returns_pdf(self):
        self.client.force_login(self.user)
        html = (
            "<h1>Pasta Carbonara</h1>"
            "<p>A classic Italian dish.</p>"
            "<h2>Ingredients</h2>"
            "<ul><li>200g spaghetti</li><li>100g pancetta</li></ul>"
            "<h2>Instructions</h2>"
            "<ol><li>Boil pasta.</li><li>Fry pancetta until crispy.</li></ol>"
            "<blockquote>Tip: use guanciale for authenticity.</blockquote>"
        )
        response = self._post({"html": html, "title": "Pasta Carbonara"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("pasta-carbonara", response["Content-Disposition"])
        self.assertIn("attachment", response["Content-Disposition"])

    def test_filename_is_sanitized(self):
        self.client.force_login(self.user)
        response = self._post({"html": "<h1>Recipe</h1>", "title": "My Recipe!! 2024"})
        self.assertEqual(response.status_code, 200)
        disposition = response["Content-Disposition"]
        self.assertNotIn("!!", disposition)
        filename = disposition.split('filename="')[1].rstrip('"')
        self.assertRegex(filename, r"^[a-z0-9\-]+\.pdf$")

    def test_empty_title_uses_recipe_fallback(self):
        self.client.force_login(self.user)
        response = self._post({"html": "<h1>Dish</h1>", "title": "---"})
        self.assertEqual(response.status_code, 200)
        # "---" → stripped all non-alphanumeric → empty → falls back to "recipe"
        self.assertIn("recipe", response["Content-Disposition"])

    def test_pdf_content_is_non_empty(self):
        self.client.force_login(self.user)
        response = self._post({"html": "<h1>Stew</h1><p>Hearty stew.</p>", "title": "Stew"})
        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(response.content), 100)
