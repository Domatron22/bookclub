# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Domatron22
"""Mirror submitted feedback into a GitHub issue.

Configured through the environment, like the rest of the app's settings:

    GITHUB_TOKEN   a token with `issues: write` on the target repo
    GITHUB_REPO    "owner/name" — defaults to this project's repo

The token is only ever read server-side. When it is unset, or the API call
fails for any reason, `create_issue` returns None: the caller still stores the
feedback row and the UI simply drops the ticket reference from its confirmation
rather than inventing one.
"""
import logging
import os

import requests

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
DEFAULT_REPO = "Domatron22/bookclub"
TIMEOUT_SECONDS = 5

# Feedback kind → issue label.
KIND_LABELS = {
    "idea": "enhancement",
    "bug": "bug",
    "confusing": "ux",
    "praise": "praise",
}

KIND_TITLES = {
    "idea": "Idea",
    "bug": "Something broke",
    "confusing": "Confusing",
    "praise": "Kind words",
}


def is_configured() -> bool:
    return bool(os.getenv("GITHUB_TOKEN"))


def build_body(feedback) -> str:
    """Compose the issue body from the feedback row."""
    lines = []
    if feedback.details:
        lines.append(feedback.details.strip())
        lines.append("")

    lines.append("---")
    lines.append(f"**Kind:** {KIND_TITLES.get(feedback.kind, feedback.kind)}")

    if feedback.include_context:
        if feedback.screen_label:
            lines.append(f"**Screen:** {feedback.screen_label}")
        if feedback.user_agent:
            lines.append(f"**Browser:** `{feedback.user_agent}`")
    if feedback.created_at:
        lines.append(f"**Submitted:** {feedback.created_at.isoformat(timespec='seconds')} UTC")

    lines.append("")
    lines.append("_Filed automatically from Coverbound's in-app feedback form._")
    return "\n".join(lines)


def create_issue(feedback) -> "int | None":
    """Create the issue and return its number, or None if that wasn't possible."""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        logger.info("GITHUB_TOKEN unset — storing feedback %s without an issue", feedback.id)
        return None

    repo = os.getenv("GITHUB_REPO", DEFAULT_REPO)
    body = build_body(feedback)

    def post(payload):
        return requests.post(
            f"{GITHUB_API}/repos/{repo}/issues",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            json=payload,
            timeout=TIMEOUT_SECONDS,
        )

    try:
        label = KIND_LABELS.get(feedback.kind, "enhancement")
        response = post({"title": feedback.summary, "body": body, "labels": [label]})
        if response.status_code == 201:
            return response.json().get("number")

        # A label the repo doesn't define comes back as 422. Losing the report
        # over a missing label would be absurd — retry without one.
        if response.status_code == 422:
            retry = post({"title": feedback.summary, "body": body})
            if retry.status_code == 201:
                return retry.json().get("number")

        logger.warning(
            "GitHub issue creation failed for feedback %s: %s %s",
            feedback.id, response.status_code, response.text[:200],
        )
    except requests.RequestException as exc:
        logger.warning("GitHub issue creation errored for feedback %s: %s", feedback.id, exc)

    return None
