from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class ReviewMetrics:
    """Tracks aggregate metrics for PR comprehension reviews."""

    total_reviews: int = 0
    passed: int = 0
    failed: int = 0
    total_questions_generated: int = 0
    total_answers_graded: int = 0
    avg_questions_per_pr: float = 0.0
    _question_counts: list[int] = field(default_factory=list, repr=False)
    last_review_at: datetime | None = None

    def record_questions_generated(self, count: int) -> None:
        self.total_questions_generated += count
        self._question_counts.append(count)
        self.avg_questions_per_pr = (
            sum(self._question_counts) / len(self._question_counts)
        )

    def record_review_result(self, passed: bool, num_answers: int) -> None:
        self.total_reviews += 1
        self.total_answers_graded += num_answers
        self.last_review_at = datetime.now(timezone.utc)
        if passed:
            self.passed += 1
        else:
            self.failed += 1

    @property
    def pass_rate(self) -> float:
        if self.total_reviews == 0:
            return 0.0
        return round(self.passed / self.total_reviews * 100, 1)

    def to_dict(self) -> dict:
        return {
            "total_reviews": self.total_reviews,
            "passed": self.passed,
            "failed": self.failed,
            "pass_rate_pct": self.pass_rate,
            "total_questions_generated": self.total_questions_generated,
            "total_answers_graded": self.total_answers_graded,
            "avg_questions_per_pr": round(self.avg_questions_per_pr, 1),
            "last_review_at": (
                self.last_review_at.isoformat() if self.last_review_at else None
            ),
        }


# Global instance — resets on server restart (in-memory only)
metrics = ReviewMetrics()
