import os
import requests
import time
import logging

logger = logging.getLogger(__name__)

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

def parse_repo_url(repo_url: str):
    """
    Extract owner/repo from https://github.com/owner/repo or similar.
    """
    parts = repo_url.rstrip("/").split("/")
    if "github.com" in parts:
        idx = parts.index("github.com")
        if len(parts) > idx + 2:
            return f"{parts[idx+1]}/{parts[idx+2]}"
    # Fallback or simple retrieval if just passed as owner/repo
    if len(parts) >= 2:
        return f"{parts[-2]}/{parts[-1]}"
    return None

def get_latest_workflow_run(repo_url: str, branch_name: str):
    """
    Get the latest workflow run for a specific branch.
    """
    if not GITHUB_TOKEN:
        logger.warning("GITHUB_TOKEN not set. CI monitoring disabled.")
        return None

    repo_full_name = parse_repo_url(repo_url)
    if not repo_full_name:
        return None

    url = f"https://api.github.com/repos/{repo_full_name}/actions/runs"
    params = {"branch": branch_name, "event": "push", "per_page": 1}
    
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        response.raise_for_status()
        data = response.json()
        runs = data.get("workflow_runs", [])
        if runs:
            return runs[0]
        return None
    except Exception as e:
        logger.error(f"Error fetching workflow runs: {e}")
        return None

def get_workflow_logs(repo_url: str, run_id: str):
    """
    Download logs for a specific workflow run.
    """
    if not GITHUB_TOKEN:
        return None
        
    repo_full_name = parse_repo_url(repo_url)
    if not repo_full_name:
        return None

    url = f"https://api.github.com/repos/{repo_full_name}/actions/runs/{run_id}/logs"
    
    try:
        response = requests.get(url, headers=HEADERS, allow_redirects=True)
        if response.status_code == 200:
            return response.content # Zip content
        else:
            logger.error(f"Failed to fetch logs: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Error fetching logs: {e}")
        return None
