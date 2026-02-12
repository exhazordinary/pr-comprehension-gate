import json
import logging

import anthropic

from app.config import get_settings
from app.llm.prompts import QUESTION_GENERATION_PROMPT

logger = logging.getLogger(__name__)

MIN_QUESTIONS = 3
MAX_QUESTIONS = 5


async def generate_questions(diff_content: str, is_large: bool = False) -> list[str]:
    """Generate comprehension questions from a PR diff using Claude.

    Returns a list of 3-5 question strings.
    Falls back to generic questions on API failure.
    """
    num_questions = MAX_QUESTIONS if is_large else MIN_QUESTIONS
    prompt = QUESTION_GENERATION_PROMPT.format(
        num_questions=num_questions,
        diff_content=diff_content[:15000],  # limit context size
    )

    settings = get_settings()
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    try:
        message = await client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text
        parsed = json.loads(raw)
        questions = parsed["questions"]

        if not isinstance(questions, list) or not (MIN_QUESTIONS <= len(questions) <= MAX_QUESTIONS):
            logger.warning("LLM returned %d questions, expected %d-%d", len(questions), MIN_QUESTIONS, MAX_QUESTIONS)
            questions = questions[:MAX_QUESTIONS] or _fallback_questions()

        return questions

    except (json.JSONDecodeError, KeyError, anthropic.APIError) as exc:
        logger.error("Question generation failed: %s", exc)
        return _fallback_questions()


def _fallback_questions() -> list[str]:
    return [
        "What is the primary purpose of this change?",
        "Are there any edge cases that this change does not handle?",
        "How does this change interact with the existing codebase?",
    ]
