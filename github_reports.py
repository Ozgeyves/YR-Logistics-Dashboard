import base64
from io import BytesIO
from pathlib import Path
from typing import List

import requests
import streamlit as st

from config import LOCAL_REPORTS_DIR


def _github_settings():
    try:
        token = st.secrets["GITHUB_TOKEN"]
        repo = st.secrets["GITHUB_REPO"]  # örn. kullanici/repo
        branch = st.secrets.get("GITHUB_BRANCH", "main")
        folder = st.secrets.get("GITHUB_REPORTS_FOLDER", "reports")
        return token, repo, branch, folder
    except Exception:
        return None


def _headers(token: str):
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def list_reports() -> List[str]:
    settings = _github_settings()
    if not settings:
        return sorted([p.name for p in LOCAL_REPORTS_DIR.glob("*.xlsx")], reverse=True)

    token, repo, branch, folder = settings
    url = f"https://api.github.com/repos/{repo}/contents/{folder}"
    response = requests.get(url, headers=_headers(token), params={"ref": branch}, timeout=30)

    if response.status_code == 404:
        return []
    response.raise_for_status()

    files = [
        item["name"]
        for item in response.json()
        if item.get("type") == "file" and item["name"].lower().endswith(".xlsx")
    ]
    return sorted(files, reverse=True)


def load_report(filename: str) -> bytes:
    settings = _github_settings()
    if not settings:
        return (LOCAL_REPORTS_DIR / filename).read_bytes()

    token, repo, branch, folder = settings
    url = f"https://api.github.com/repos/{repo}/contents/{folder}/{filename}"
    response = requests.get(url, headers=_headers(token), params={"ref": branch}, timeout=30)
    response.raise_for_status()
    payload = response.json()
    return base64.b64decode(payload["content"])


def save_report(filename: str, content: bytes) -> str:
    if not filename.lower().endswith(".xlsx"):
        filename += ".xlsx"

    settings = _github_settings()
    if not settings:
        target = LOCAL_REPORTS_DIR / filename
        if target.exists():
            stem = target.stem
            suffix = target.suffix
            index = 2
            while target.exists():
                target = LOCAL_REPORTS_DIR / f"{stem}_v{index}{suffix}"
                index += 1
        target.write_bytes(content)
        return target.name

    token, repo, branch, folder = settings
    path = f"{folder}/{filename}"
    url = f"https://api.github.com/repos/{repo}/contents/{path}"

    existing_sha = None
    get_response = requests.get(url, headers=_headers(token), params={"ref": branch}, timeout=30)
    if get_response.status_code == 200:
        existing_sha = get_response.json().get("sha")
    elif get_response.status_code != 404:
        get_response.raise_for_status()

    payload = {
        "message": f"Add dashboard report: {filename}",
        "content": base64.b64encode(content).decode("ascii"),
        "branch": branch,
    }
    if existing_sha:
        payload["sha"] = existing_sha

    response = requests.put(url, headers=_headers(token), json=payload, timeout=60)
    response.raise_for_status()
    return filename
