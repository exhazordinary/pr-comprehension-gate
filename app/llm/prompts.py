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

GRADE_ANSWERS_PROMPT = """\
You are grading a code reviewer's comprehension of a pull request. Your job is to \
determine whether the reviewer actually read and understood the code changes — not \
whether they wrote a perfect essay.

## Grading Philosophy
- **Conceptual understanding over exact wording.** Accept answers that demonstrate \
genuine understanding even if they use different terminology than the diff.
- **Require specificity.** Vague answers like "it improves the code" or "for better \
performance" without referencing actual changes MUST fail. The reviewer should cite \
concrete details from the diff (function names, logic branches, variable changes, etc.).
- **Partial knowledge is a PASS if the core insight is correct.** If a reviewer gets \
the main point right but misses a minor edge case, that is a PASS with feedback noting \
the gap. If they miss the central point entirely, that is a FAIL.
- **Wrong is wrong.** If an answer contains a factual misunderstanding of the code \
(e.g., says a function returns X when it returns Y), that is a FAIL regardless of \
how confident the answer sounds.

## Pass Threshold
At least 80% of answers must be graded PASS for overall_pass to be true. \
For 3 questions: 3/3 required. For 4 questions: 3/4. For 5 questions: 4/5.

## Inputs

PR Diff:
{diff_content}

Questions Asked:
{questions_json}

Reviewer's Answers:
{answers_json}

## Output

Grade each answer as PASS or FAIL. Provide brief, constructive feedback for each \
(1-2 sentences — helpful for learning, not punitive). Write a 1-sentence summary of \
the overall assessment.

Respond with ONLY a JSON object in this exact format (no markdown fencing):
{{
  "overall_pass": true,
  "answers": [
    {{"question": "Q1", "answer": "A1", "grade": "PASS", "feedback": "Correct — ..."}},
    {{"question": "Q2", "answer": "A2", "grade": "FAIL", "feedback": "The change actually ..."}}
  ],
  "summary": "Reviewer demonstrated solid understanding of ..."
}}
"""
