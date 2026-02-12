import httpx

API_BASE = "https://api.github.com"
COMMON_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def _auth_headers(token: str) -> dict[str, str]:
    return {**COMMON_HEADERS, "Authorization": f"Bearer {token}"}


async def fetch_pr_files(
    owner: str, repo: str, pr_number: int, token: str
) -> list[dict]:
    """Fetch the list of changed files for a PR (includes patch diffs)."""
    url = f"{API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/files"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=_auth_headers(token), params={"per_page": 100})
        resp.raise_for_status()
    return resp.json()


async def post_pr_comment(
    owner: str, repo: str, pr_number: int, body: str, token: str
) -> dict:
    """Post a comment on a PR. Returns the created comment object."""
    url = f"{API_BASE}/repos/{owner}/{repo}/issues/{pr_number}/comments"
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=_auth_headers(token), json={"body": body})
        resp.raise_for_status()
    return resp.json()


async def set_commit_status(
    owner: str,
    repo: str,
    sha: str,
    state: str,
    description: str,
    token: str,
    target_url: str | None = None,
) -> dict:
    """Set a commit status check.

    state: "pending" | "success" | "failure" | "error"
    """
    url = f"{API_BASE}/repos/{owner}/{repo}/statuses/{sha}"
    payload = {
        "state": state,
        "context": "PR-Comprehension-Check",
        "description": description[:140],
    }
    if target_url:
        payload["target_url"] = target_url

    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=_auth_headers(token), json=payload)
        resp.raise_for_status()
    return resp.json()
