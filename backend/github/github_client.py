"""
backend/github/github_client.py
=================================
GitHub integration — reads repo info, pushes branches, reads CI logs.
Uses PyGithub + GitPython. All operations are non-destructive to main.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from github import Github, GithubException, Repository

from backend.utils.logger import logger
from config.settings import settings


class GitHubClient:
    """
    Wraps PyGithub and GitPython for:
    - Reading repo metadata
    - Fetching CI/Actions logs
    - Pushing AI healing branch
    - Creating pull request
    """

    def __init__(self, token: Optional[str] = None):
        token = token or settings.GITHUB_TOKEN
        if not token:
            logger.warning("[GitHubClient] No GitHub token — operating in read-only/local mode")
            self.gh = None
        else:
            self.gh = Github(token)

    # ─────────────────────────────────────────
    def get_repo(self, repo_slug: str) -> Optional[Repository.Repository]:
        """e.g. repo_slug = 'owner/repo-name'"""
        if not self.gh:
            return None
        try:
            return self.gh.get_repo(repo_slug)
        except GithubException as e:
            logger.error(f"[GitHubClient] Cannot access repo {repo_slug}: {e}")
            return None

    def fetch_ci_logs(self, repo_slug: str, run_id: int) -> Optional[str]:
        """Fetch the raw logs for a specific workflow run."""
        repo = self.get_repo(repo_slug)
        if not repo:
            return None

        try:
            run = repo.get_workflow_run(run_id)
            logs_url = run.logs_url
            import requests
            headers = {"Authorization": f"token {settings.GITHUB_TOKEN}"}
            response = requests.get(logs_url, headers=headers, timeout=30)
            if response.status_code == 200:
                return response.text
            else:
                logger.warning(f"[GitHubClient] Logs fetch returned {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"[GitHubClient] Failed to fetch CI logs: {e}")
            return None

    def push_branch(self, repo_path: str, branch_name: str) -> bool:
        """Push the local healing branch to remote."""
        try:
            import git
            repo = git.Repo(repo_path)
            origin = repo.remote("origin")
            origin.push(refspec=f"{branch_name}:{branch_name}")
            logger.success(f"[GitHubClient] Pushed branch '{branch_name}' to remote")
            return True
        except Exception as e:
            logger.error(f"[GitHubClient] Push failed: {e}")
            return False

    def create_pull_request(
        self,
        repo_slug: str,
        head_branch: str,
        base_branch: str = "main",
        title: str = "[AI-AGENT] Autonomous CI Healing",
        body: str = "Automatically generated fixes by the CI/CD Healing Intelligence Core.",
    ) -> Optional[str]:
        """Create a PR from the AI healing branch to main."""
        repo = self.get_repo(repo_slug)
        if not repo:
            return None

        try:
            pr = repo.create_pull(
                title=title,
                body=body,
                head=head_branch,
                base=base_branch,
            )
            logger.success(f"[GitHubClient] PR created: {pr.html_url}")
            return pr.html_url
        except GithubException as e:
            logger.error(f"[GitHubClient] PR creation failed: {e}")
            return None
