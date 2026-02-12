import json
import logging

from openai import AsyncOpenAI

from app.config import get_settings
from app.llm.prompts import QUESTION_GENERATION_PROMPT

logger = logging.getLogger(__name__)

MIN_QUESTIONS = 3
MAX_QUESTIONS = 5


async def generate_questions(diff_content: str, is_large: bool = False) -> list[str]:
    """Generate comprehension questions from a PR diff via OpenRouter.

    Returns a list of 3-5 question strings.
    Falls back to generic questions on API failure.
    """
    num_questions = MAX_QUESTIONS if is_large else MIN_QUESTIONS
    prompt = QUESTION_GENERATION_PROMPT.format(
        num_questions=num_questions,
        diff_content=diff_content[:15000],
    )

    settings = get_settings()
    client = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.openrouter_api_key,
    )

    try:
        response = await client.chat.completions.create(
            model=settings.llm_model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.choices[0].message.content
        parsed = json.loads(raw)
        questions = parsed["questions"]

        if not isinstance(questions, list) or not (MIN_QUESTIONS <= len(questions) <= MAX_QUESTIONS):
            logger.warning("LLM returned %d questions, expected %d-%d", len(questions), MIN_QUESTIONS, MAX_QUESTIONS)
            questions = questions[:MAX_QUESTIONS] or _fallback_questions()

        return questions

    except (json.JSONDecodeError, KeyError, Exception) as exc:
        logger.error("Question generation failed: %s", exc)
        return _fallback_questions()


def _fallback_questions() -> list[str]:
    return [
        "What is the primary purpose of this change?",
        "Are there any edge cases that this change does not handle?",
        "How does this change interact with the existing codebase?",
    ]
