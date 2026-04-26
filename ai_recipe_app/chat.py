from collections.abc import Iterator
from langchain_mistralai import ChatMistralAI
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage
from langchain_core.output_parsers import StrOutputParser
from django.conf import settings
from loguru import logger
from .prompt import RECIPE_SYSTEM_PROMPT


logger.info(
    "Initialising ChatMistralAI | model={} temperature=0 max_retries=2",
    settings.MISTRAL_MODEL,
)
LLM = ChatMistralAI(
    model=settings.MISTRAL_MODEL,
    temperature=0,
    max_retries=2,
)
logger.success("ChatMistralAI ready | model={}", settings.MISTRAL_MODEL)

_parser = StrOutputParser()


def stream_recipe(
    dish_name: str,
    language: str = "English",
    history: list[BaseMessage] | None = None,
) -> Iterator[str]:
    """Yield recipe tokens, including prior conversation turns for context."""
    history = history or []
    logger.info(
        "stream_recipe START | dish={!r} language={} history_turns={}",
        dish_name, language, len(history),
    )

    messages: list[BaseMessage] = [
        SystemMessage(content=RECIPE_SYSTEM_PROMPT.format(language=language)),
        *history,
        HumanMessage(content=dish_name),
    ]

    token_count = 0
    try:
        for chunk in (LLM | _parser).stream(messages):
            token_count += 1
            yield chunk
        logger.success(
            "stream_recipe DONE  | dish={!r} tokens_streamed={}",
            dish_name, token_count,
        )
    except Exception:
        logger.exception("stream_recipe ERROR | dish={!r}", dish_name)
        raise
