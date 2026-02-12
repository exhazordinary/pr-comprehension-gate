import hashlib
import json
import logging
import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from sqlalchemy import select

from app.config import get_settings
from app.github.api_client import fetch_pr_files, post_pr_comment, set_commit_status
from app.github.auth import get_installation_token
from app.github.diff_parser import parse_pr_diff
from app.llm.answer_grader import grade_answers
from app.llm.question_generator import generate_questions
from app.models.database import async_session, init_db
from app.models.schemas import PRReview
from app.utils.security import verify_github_signature

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("Database initialized")
    yield


app = FastAPI(title="PR Comprehension Gate", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/webhooks/github")
async def webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str | None = Header(None),
    x_github_event: str | None = Header(None),
    x_github_delivery: str | None = Header(None),
):
    body = await request.body()
    settings = get_settings()

    if not verify_github_signature(body, x_hub_signature_256, settings.webhook_secret):
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = json.loads(body)

    if x_github_event == "pull_request":
        action = payload.get("action")
        if action in ("opened", "synchronize", "reopened"):
            background_tasks.add_task(handle_pr_event, payload)

    elif x_github_event == "issue_comment":
        if payload.get("action") == "created":
            issue = payload.get("issue", {})
            if "pull_request" in issue:
                background_tasks.add_task(handle_comment_event, payload)

    return {"status": "ok", "delivery": x_github_delivery}


# ---------------------------------------------------------------------------
# PR Event Handler
# ---------------------------------------------------------------------------

async def handle_pr_event(payload: dict) -> None:
    try:
        pr = payload["pull_request"]
        repo = payload["repository"]
        installation_id = payload["installation"]["id"]

        # Skip draft PRs
        if pr.get("draft", False):
            logger.info("Skipping draft PR #%s", pr["number"])
            return

        owner = repo["owner"]["login"]
        repo_name = repo["name"]
        pr_number = pr["number"]
        pr_sha = pr["head"]["sha"]
        pr_id = f"{owner}/{repo_name}#{pr_number}"

        token = await get_installation_token(installation_id)

        # Fetch and parse diff
        files = await fetch_pr_files(owner, repo_name, pr_number, token)
        diff_content, diff_hash, is_large = parse_pr_diff(files)

        if diff_content == "(no meaningful code changes)":
            await set_commit_status(
                owner, repo_name, pr_sha, "success",
                "No code changes to review", token,
            )
            return

        # Check if we already have questions for this exact diff
        async with async_session() as session:
            existing = (await session.execute(
                select(PRReview).where(PRReview.pr_id == pr_id)
            )).scalar_one_or_none()

            if existing and existing.diff_hash == diff_hash:
                logger.info("Diff unchanged for %s, skipping question regeneration", pr_id)
                return

        # Generate questions
        questions = await generate_questions(diff_content, is_large)

        # Format comment
        q_list = "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))
        large_warning = (
            "\n> **Note:** This is a large PR. Questions focus on the most critical changes.\n"
            if is_large else ""
        )
        comment_body = (
            f"## PR Comprehension Check\n\n"
            f"Please answer the following questions to verify your understanding "
            f"of these changes:\n\n"
            f"{large_warning}"
            f"{q_list}\n\n"
            f"---\n"
            f"**How to respond:** Reply to this comment with your answers "
            f"numbered 1\u2013{len(questions)}.\n\n"
            f"Status: \u23f3 Awaiting reviewer answers"
        )

        # Post comment and store state
        comment = await post_pr_comment(owner, repo_name, pr_number, comment_body, token)

        async with async_session() as session:
            if existing:
                existing.pr_sha = pr_sha
                existing.questions = questions
                existing.diff_hash = diff_hash
                existing.status = "pending_review"
                existing.reviewer_answers = None
                existing.grading_result = None
                existing.reviewer_username = None
                existing.bot_comment_id = comment["id"]
                existing.reviewed_at = None
                session.add(existing)
            else:
                review = PRReview(
                    pr_id=pr_id,
                    pr_sha=pr_sha,
                    installation_id=installation_id,
                    questions=questions,
                    diff_hash=diff_hash,
                    status="pending_review",
                    bot_comment_id=comment["id"],
                )
                session.add(review)
            await session.commit()

        # Set pending status
        await set_commit_status(
            owner, repo_name, pr_sha, "pending",
            "Awaiting reviewer comprehension answers", token,
        )
        logger.info("Posted %d questions for %s", len(questions), pr_id)

    except Exception:
        logger.exception("Error handling PR event")


# ---------------------------------------------------------------------------
# Comment Event Handler
# ---------------------------------------------------------------------------

ANSWER_PATTERN = re.compile(r"^\s*(\d+)\.\s*(.+)", re.MULTILINE)


def parse_numbered_answers(body: str) -> list[str]:
    matches = ANSWER_PATTERN.findall(body)
    if not matches:
        return []
    # Sort by number and extract answer text
    sorted_answers = sorted(matches, key=lambda m: int(m[0]))
    return [text.strip() for _, text in sorted_answers]


async def handle_comment_event(payload: dict) -> None:
    try:
        comment = payload["comment"]
        issue = payload["issue"]
        repo = payload["repository"]
        installation_id = payload["installation"]["id"]

        comment_author = comment["user"]["login"]
        comment_body = comment["body"]

        # Ignore bot's own comments
        if comment["user"].get("type") == "Bot":
            logger.info("Ignoring bot comment from %s", comment_author)
            return

        owner = repo["owner"]["login"]
        repo_name = repo["name"]
        pr_number = issue["number"]
        pr_id = f"{owner}/{repo_name}#{pr_number}"
        logger.info("Processing comment on %s from %s", pr_id, comment_author)

        # Look up the review record
        async with async_session() as session:
            review = (await session.execute(
                select(PRReview).where(PRReview.pr_id == pr_id)
            )).scalar_one_or_none()

        if not review:
            logger.info("No review record for %s, ignoring", pr_id)
            return  # not a tracked PR

        if review.status == "passed":
            logger.info("PR %s already passed, ignoring", pr_id)
            return  # already passed, don't re-grade

        # Parse answers
        logger.info("Comment body: %s", comment_body[:200])
        answers = parse_numbered_answers(comment_body)
        logger.info("Parsed %d answers from comment", len(answers))
        expected_count = len(review.questions)

        if len(answers) < expected_count:
            token = await get_installation_token(installation_id)
            await post_pr_comment(
                owner, repo_name, pr_number,
                f"I found {len(answers)} answer(s) but expected {expected_count}. "
                f"Please reply with all answers in numbered format:\n"
                f"```\n1. Your answer\n2. Your answer\n...\n```",
                token,
            )
            return

        answers = answers[:expected_count]  # trim extra answers
        token = await get_installation_token(installation_id)

        # Re-fetch diff for grading context
        files = await fetch_pr_files(owner, repo_name, pr_number, token)
        diff_content, _, _ = parse_pr_diff(files)

        # Grade
        result = await grade_answers(diff_content, review.questions, answers)

        # Update database
        async with async_session() as session:
            review = (await session.execute(
                select(PRReview).where(PRReview.pr_id == pr_id)
            )).scalar_one_or_none()
            review.reviewer_answers = answers
            review.grading_result = {
                "overall_pass": result.overall_pass,
                "answers": result.answers,
                "summary": result.summary,
            }
            review.status = "passed" if result.overall_pass else "failed"
            review.reviewer_username = comment_author
            review.reviewed_at = datetime.now(timezone.utc)
            session.add(review)
            await session.commit()

        # Build feedback comment
        if result.overall_pass:
            status_header = "## \u2705 Comprehension Check Passed"
            status_line = f"@{comment_author}, your answers demonstrate solid understanding. The PR is now eligible for merging."
        else:
            status_header = "## \u274c Comprehension Check Failed"
            status_line = (
                f"@{comment_author}, some answers indicate gaps in understanding. "
                f"Please review the code more carefully and reply with revised answers."
            )

        feedback_lines = []
        for item in result.answers:
            icon = "\u2705" if item.get("grade") == "PASS" else "\u274c"
            feedback_lines.append(
                f"**{icon} Q:** {item.get('question', 'N/A')}\n"
                f"**A:** {item.get('answer', 'N/A')}\n"
                f"**Feedback:** {item.get('feedback', '')}\n"
            )

        feedback_body = (
            f"{status_header}\n\n"
            f"{status_line}\n\n"
            f"---\n\n"
            + "\n".join(feedback_lines)
            + f"\n---\n**Summary:** {result.summary}"
        )

        await post_pr_comment(owner, repo_name, pr_number, feedback_body, token)

        # Set status check
        if result.overall_pass:
            await set_commit_status(
                owner, repo_name, review.pr_sha, "success",
                "Reviewer comprehension verified", token,
            )
        else:
            await set_commit_status(
                owner, repo_name, review.pr_sha, "failure",
                "Comprehension check failed — re-review required", token,
            )

        logger.info("Graded %s: %s", pr_id, "PASS" if result.overall_pass else "FAIL")

    except Exception:
        logger.exception("Error handling comment event")
