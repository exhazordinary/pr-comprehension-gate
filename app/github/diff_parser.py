import hashlib

# Files to skip when generating comprehension questions
SKIP_PATTERNS = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "Cargo.lock",
    "poetry.lock",
    "Pipfile.lock",
    ".gitignore",
}

SKIP_EXTENSIONS = {".min.js", ".min.css", ".map", ".svg", ".png", ".jpg", ".ico"}

MAX_TOTAL_LINES = 5000
MAX_FILE_PATCH_LINES = 500


def parse_pr_diff(files_payload: list[dict]) -> tuple[str, str, bool]:
    """Extract meaningful diff content from GitHub PR files payload.

    Returns:
        (formatted_diff, diff_hash, is_large)
        - formatted_diff: human-readable diff string for LLM consumption
        - diff_hash: SHA256 of the diff for change detection
        - is_large: True if the PR exceeds size thresholds
    """
    parts: list[str] = []
    total_lines = 0
    is_large = False

    for file_obj in files_payload:
        filename = file_obj.get("filename", "")

        # Skip non-code files
        if _should_skip(filename):
            continue

        patch = file_obj.get("patch", "")
        if not patch:
            continue

        patch_lines = patch.count("\n") + 1
        total_lines += patch_lines

        if total_lines > MAX_TOTAL_LINES:
            is_large = True
            break

        # Truncate very long individual file patches
        if patch_lines > MAX_FILE_PATCH_LINES:
            lines = patch.split("\n")[:MAX_FILE_PATCH_LINES]
            patch = "\n".join(lines) + "\n... (truncated)"

        status = file_obj.get("status", "modified")
        additions = file_obj.get("additions", 0)
        deletions = file_obj.get("deletions", 0)

        parts.append(
            f"### {filename} ({status}: +{additions}/-{deletions})\n```diff\n{patch}\n```"
        )

    formatted_diff = "\n\n".join(parts) if parts else "(no meaningful code changes)"
    diff_hash = hashlib.sha256(formatted_diff.encode()).hexdigest()

    return formatted_diff, diff_hash, is_large


def _should_skip(filename: str) -> bool:
    basename = filename.rsplit("/", 1)[-1] if "/" in filename else filename
    if basename in SKIP_PATTERNS:
        return True
    return any(filename.endswith(ext) for ext in SKIP_EXTENSIONS)
