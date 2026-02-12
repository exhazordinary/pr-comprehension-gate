import json
import logging
from dataclasses import dataclass

import anthropic

from app.config import get_settings
from app.llm.prompts import GRADE_ANSWERS_PROMPT

logger = logging.getLogger(__name__)


@dataclass
class GradingResult:
    overall_pass: bool
    answers: list[dict]  # [{"question": ..., "answer": ..., "grade": "PASS"|"FAIL", "feedback": ...}]
    summary: str


async def grade_answers(
    diff_content: str,
    questions: list[str],
    answers: list[str],
) -> GradingResult:
    """Grade reviewer answers against the PR diff using Claude.

    Returns a GradingResult with per-answer feedback and overall pass/fail.
    """
    prompt = GRADE_ANSWERS_PROMPT.format(
        diff_content=diff_content[:15000],
        questions_json=json.dumps(questions),
        answers_json=json.dumps(answers),
    )

    settings = get_settings()
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    try:
        message = await client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text
        parsed = json.loads(raw)

        return GradingResult(
            overall_pass=parsed["overall_pass"],
            answers=parsed["answers"],
            summary=parsed["summary"],
        )

    except (json.JSONDecodeError, KeyError, anthropic.APIError) as exc:
        logger.error("Answer grading failed: %s", exc)
        return GradingResult(
            overall_pass=False,
            answers=[],
            summary="Grading failed due to a system error. Please try again.",
        )
