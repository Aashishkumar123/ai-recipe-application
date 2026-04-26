from collections.abc import Iterator
from langchain_mistralai import ChatMistralAI
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage
from langchain_core.output_parsers import StrOutputParser
from django.conf import settings
from .prompt import RECIPE_SYSTEM_PROMPT

LLM = ChatMistralAI(
    model=settings.MISTRAL_MODEL,
    temperature=0,
    max_retries=2,
)

_parser = StrOutputParser()

def stream_recipe(
    dish_name: str,
    language: str = "English",
    history: list[BaseMessage] | None = None,
) -> Iterator[str]:
    """Yield recipe tokens, including prior conversation turns for context."""
    messages: list[BaseMessage] = [
        SystemMessage(content=RECIPE_SYSTEM_PROMPT.format(language=language)),
        *(history or []),
        HumanMessage(content=dish_name),
    ]
    for chunk in (LLM | _parser).stream(messages):
        yield chunk
