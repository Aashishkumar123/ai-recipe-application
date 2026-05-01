from collections.abc import Iterator
# from langchain_mistralai import ChatMistralAI
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage
from langchain_core.output_parsers import StrOutputParser
from django.conf import settings
from loguru import logger
from .prompt import RECIPE_SYSTEM_PROMPT, USER_PROFILE_BLOCK
from langchain_openai import AzureChatOpenAI


logger.info(
    "Initialising AzureChatOpenAI | model={} temperature=0 max_retries=2",
    settings.AZURE_DEPLOYMENT_NAME,
)

llm = AzureChatOpenAI(
    api_key= settings.AZURE_OPENAI_API_KEY,
    azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
    azure_deployment=settings.AZURE_DEPLOYMENT_NAME,
    api_version="2025-04-01-preview",
    temperature=0.4,
    max_tokens=None,
    timeout=None,
    max_retries=2,
)
logger.success("AzureChatOpenAI ready | model={}", settings.AZURE_DEPLOYMENT_NAME)

_parser = StrOutputParser()


def _build_system_prompt(language: str, user=None) -> str:
    base = RECIPE_SYSTEM_PROMPT.format(language=language)

    if user is None or not user.is_authenticated:
        return base

    lines = []
    if user.cooking_skill:
        lines.append(f"- Cooking skill: {user.cooking_skill.capitalize()}")
    if user.default_servings:
        lines.append(f"- Default serving size: {user.default_servings}")
    if user.dietary_restrictions:
        restrictions = ", ".join(r.title() for r in user.dietary_restrictions)
        lines.append(f"- Dietary restrictions: {restrictions}")
    if user.cuisine_preferences:
        cuisines = ", ".join(c.title() for c in user.cuisine_preferences)
        lines.append(f"- Preferred cuisines: {cuisines}")

    if not lines:
        return base

    profile_block = "\n".join(lines)
    return base + USER_PROFILE_BLOCK.format(profile_block=profile_block)


def stream_recipe(
    dish_name: str,
    language: str = "English",
    history: list[BaseMessage] | None = None,
    user=None,
) -> Iterator[str]:
    """Yield recipe tokens, including prior conversation turns for context."""
    history = history or []
    logger.info(
        "stream_recipe START | dish={!r} language={} history_turns={} user={}",
        dish_name, language, len(history), user,
    )

    system_prompt = _build_system_prompt(language, user)
    messages: list[BaseMessage] = [
        SystemMessage(content=system_prompt),
        *history,
        HumanMessage(content=dish_name),
    ]

    sep = "=" * 60
    history_block = "".join(
        f"[{msg.__class__.__name__.replace('Message', '').upper()}]\n{msg.content}\n{sep}\n"
        for msg in history
    )
    logger.debug(
        "stream_recipe PROMPT\n{sep}\n[SYSTEM]\n{system}\n{sep}\n{history}[USER]\n{user}\n{sep}",
        sep=sep,
        system=system_prompt,
        history=history_block,
        user=dish_name,
    )

    token_count = 0
    chunks = ""
    try:
        for chunk in (llm | _parser).stream(messages):
            token_count += 1
            chunks += chunk
            yield chunk
        logger.success(
            "stream_recipe DONE  | dish={!r} tokens_streamed={}",
            dish_name, token_count,
        )
        logger.debug("stream_recipe FINAL OUTPUT\n{sep}\n{output}\n{sep}", sep=sep, output=chunks)
    except Exception:
        logger.exception("stream_recipe ERROR | dish={!r}", dish_name)
        raise
