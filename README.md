# PR Comprehension Gate

A GitHub App that verifies reviewer comprehension instead of auto-summarizing code. When a pull request is opened, the bot generates 3-5 comprehension questions based on the diff. Reviewers must answer correctly for the PR to become mergeable.

## How It Works

```
1. Developer opens a PR
2. Bot reads the diff and generates comprehension questions via LLM
3. Bot posts questions as a PR comment and sets status to "pending"
4. Reviewer replies with numbered answers
5. Bot grades answers via LLM (80% pass threshold)
6. Status check updates: success (merge allowed) or failure (re-review required)
```

### Demo

**Questions posted:**

> **PR Comprehension Check**
>
> 1. How does `avg_questions_per_pr` behave if `_question_counts` is empty?
> 2. Why was in-memory chosen for metric persistence?
> 3. How might floating point precision affect `pass_rate`?

**After answering:**

> **Comprehension Check Passed**
>
> Your answers demonstrate solid understanding. The PR is now eligible for merging.

## Architecture

```
GitHub PR Event ──→ Webhook ──→ FastAPI ──→ LLM (generate questions)
                                  │
                              SQLite (state)
                                  │
                              GitHub API (post comment + set status)

Reviewer answers ──→ Webhook ──→ FastAPI ──→ LLM (grade answers)
                                  │
                              GitHub API (pass/fail status + feedback)
```

### Key Design Decisions

- **BackgroundTasks** — GitHub requires 200 OK within 10 seconds. LLM calls take 5-10s. The webhook responds immediately and processes asynchronously.
- **OpenRouter** — Single API key, any model. Currently using `google/gemini-2.5-flash` (free). Swap models via `LLM_MODEL` env var without code changes.
- **Commit Statuses** (not Checks API) — Simpler API, works with branch protection, sufficient for pass/fail gates.
- **SQLite** — Zero-setup for development. Upgrade to PostgreSQL by changing `DATABASE_URL`.

## Project Structure

```
app/
├── main.py                  # FastAPI app, webhook endpoint, event handlers
├── config.py                # Environment config via pydantic-settings
├── metrics.py               # In-memory aggregate review metrics
├── github/
│   ├── auth.py              # GitHub App JWT + installation token caching
│   ├── api_client.py        # Async GitHub API client (httpx)
│   └── diff_parser.py       # PR diff extraction and filtering
├── llm/
│   ├── prompts.py           # Question generation + grading prompt templates
│   ├── question_generator.py # Generate questions via OpenRouter
│   └── answer_grader.py     # Grade answers via OpenRouter
├── models/
│   ├── database.py          # Async SQLAlchemy + SQLite setup
│   └── schemas.py           # PRReview ORM model
└── utils/
    ├── rate_limiter.py      # In-memory sliding window rate limiter
    └── security.py          # HMAC-SHA256 webhook signature verification
```

## Setup

### 1. Create a GitHub App

Go to [github.com/settings/apps/new](https://github.com/settings/apps/new):

| Setting | Value |
|---------|-------|
| Webhook URL | `https://your-domain.com/webhooks/github` |
| Webhook secret | Generate with `python3 -c "import secrets; print(secrets.token_hex(32))"` |

**Repository permissions:**
- Contents: Read-only
- Pull requests: Read and write
- Commit statuses: Read and write
- Issues: Read-only

**Subscribe to events:**
- Pull request
- Issue comment

Download the private key (`.pem` file) after creation.

### 2. Install dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:
```
GITHUB_APP_ID=your_app_id
GITHUB_PRIVATE_KEY=<base64-encoded .pem file>
WEBHOOK_SECRET=your_webhook_secret
OPENROUTER_API_KEY=your_openrouter_key
LLM_MODEL=google/gemini-2.5-flash
```

To base64-encode your private key:
```bash
base64 -i path/to/private-key.pem | tr -d '\n'
```

### 4. Run locally

```bash
uvicorn app.main:app --reload --port 8000
```

Use [ngrok](https://ngrok.com) to expose locally:
```bash
ngrok http 8000
```

Update the GitHub App webhook URL to the ngrok URL.

### 5. Deploy to Railway

```bash
npm install -g @railway/cli
railway login
railway init --name pr-comprehension-gate
railway variables set GITHUB_APP_ID=... WEBHOOK_SECRET=... OPENROUTER_API_KEY=... LLM_MODEL=google/gemini-2.5-flash DATABASE_URL=sqlite+aiosqlite:///pr_reviews.db
railway variables set "GITHUB_PRIVATE_KEY=$(base64 -i path/to/key.pem | tr -d '\n')"
railway up
railway domain
```

Update the GitHub App webhook URL to the Railway domain.

### 6. Enable branch protection

Repository → Settings → Branches → Add rule for `main`:
- Require status checks to pass before merging
- Select: `PR-Comprehension-Check`

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/metrics` | GET | Aggregate review metrics (pass rate, counts) |
| `/webhooks/github` | POST | GitHub webhook receiver |

## Configuration

| Env Variable | Required | Description |
|-------------|----------|-------------|
| `GITHUB_APP_ID` | Yes | GitHub App ID |
| `GITHUB_PRIVATE_KEY` | Yes | Base64-encoded PEM private key |
| `WEBHOOK_SECRET` | Yes | Webhook HMAC secret |
| `OPENROUTER_API_KEY` | Yes | OpenRouter API key |
| `LLM_MODEL` | No | OpenRouter model slug (default: `google/gemini-2.5-flash`) |
| `DATABASE_URL` | No | SQLAlchemy DB URL (default: `sqlite+aiosqlite:///pr_reviews.db`) |

### Free model options on OpenRouter

| Model | Quality | Speed |
|-------|---------|-------|
| `google/gemini-2.5-flash` | Best free option | Fast |
| `deepseek/deepseek-v3.2-20251201` | Strong code understanding | Fast |
| `meta-llama/llama-4-scout` | Good general purpose | Fast |

## Edge Cases Handled

- **PR updated after questions posted** — Detects via diff hash, regenerates questions
- **Draft PRs** — Skipped, no questions posted
- **Empty PRs** — Auto-passed with success status
- **Large PRs (>1000 lines)** — Warns reviewer, focuses on key files
- **Malformed answers** — Posts clarification request with format instructions
- **Bot loop prevention** — Ignores its own comments
- **Failed answers** — Reviewer can re-answer, status updates on retry
- **LLM failures** — Falls back to generic questions, strips markdown fences

## Tech Stack

- **Python 3.10+** / **FastAPI** — Async webhook handling
- **SQLAlchemy** + **aiosqlite** — Async ORM with SQLite
- **OpenRouter** (OpenAI-compatible SDK) — LLM provider abstraction
- **httpx** — Async GitHub API client
- **PyJWT** — GitHub App authentication
- **Railway** — Deployment

## License

MIT
