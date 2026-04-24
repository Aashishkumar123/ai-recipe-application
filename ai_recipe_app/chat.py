from collections.abc import Iterator
from langchain_mistralai import ChatMistralAI
from django.conf import settings
from .prompt import RECIPE_SYSTEM_PROMPT
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

RECIPE_PROMPT = ChatPromptTemplate.from_messages(RECIPE_SYSTEM_PROMPT)
LLM = ChatMistralAI(
    model=settings.MISTRAL_MODEL,
    temperature=0,
    max_retries=2,
)

recipe_chain = RECIPE_PROMPT | LLM | StrOutputParser()

def stream_recipe(dish_name: str, language: str = "English") -> Iterator[str]:
    """Yield recipe tokens as they're generated."""
    for chunk in recipe_chain.stream({"dish_name": dish_name, "language": language}):
        yield chunk
