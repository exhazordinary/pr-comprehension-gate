from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.database import Base


class PRReview(Base):
    __tablename__ = "pr_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pr_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    pr_sha: Mapped[str] = mapped_column(String(40))
    installation_id: Mapped[int] = mapped_column(Integer)
    questions: Mapped[dict] = mapped_column(JSON)
    diff_hash: Mapped[str] = mapped_column(String(64))
    reviewer_answers: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    grading_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending_review", index=True)
    reviewer_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bot_comment_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
