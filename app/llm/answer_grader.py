import json
import logging
from dataclasses import dataclass

from openai import AsyncOpenAI

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
    """Grade reviewer answers against the PR diff via OpenRouter.

    Returns a GradingResult with per-answer feedback and overall pass/fail.
    """
    prompt = GRADE_ANSWERS_PROMPT.format(
        diff_content=diff_content[:15000],
        questions_json=json.dumps(questions),
        answers_json=json.dumps(answers),
    )

    settings = get_settings()
    client = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.openrouter_api_key,
    )

    try:
        response = await client.chat.completions.create(
            model=settings.llm_model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.choices[0].message.content
        logger.info("Grader raw LLM response: %s", raw[:500] if raw else "(empty)")
        # Strip markdown fencing if present
        cleaned = raw.strip() if raw else ""
        if cleaned.startswith("```"):
            cleaned = "\n".join(cleaned.split("\n")[1:])
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
        parsed = json.loads(cleaned)

        return GradingResult(
            overall_pass=parsed["overall_pass"],
            answers=parsed["answers"],
            summary=parsed["summary"],
        )

    except (json.JSONDecodeError, KeyError, Exception) as exc:
        logger.error("Answer grading failed: %s", exc)
        return GradingResult(
            overall_pass=False,
            answers=[],
            summary="Grading failed due to a system error. Please try again.",
        )
