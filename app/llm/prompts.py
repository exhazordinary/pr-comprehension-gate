QUESTION_GENERATION_PROMPT = """\
You are a senior code reviewer. Given the following pull request diff, generate \
{num_questions} specific comprehension questions that test whether a reviewer \
truly understands the changes being made.

Guidelines:
- Ask "why" and "how" questions, not "what changed" questions
- Test understanding of edge cases, error handling, and side effects
- Ask about interactions with existing code when relevant
- Avoid yes/no questions — require explanations
- Questions should be answerable solely from the diff context

PR Diff:
{diff_content}

Respond with ONLY a JSON object in this exact format (no markdown fencing):
{{"questions": ["Question 1?", "Question 2?", "Question 3?"]}}
"""

# TODO(human): Implement the grading prompt — GRADE_ANSWERS_PROMPT
# This prompt needs to define:
# 1. How strictly to evaluate answers (exact match vs. conceptual understanding)
# 2. What constitutes a passing vs. failing answer
# 3. How to handle partial credit
# 4. The JSON output schema for grading results
GRADE_ANSWERS_PROMPT = ""
"""
"""
