"""Small, dependency-free GitHub updater used by the installed build.

The updater is deliberately kept outside the cursor-locking code path.  It
only talks to the public CursorFence releases API over HTTPS, downloads the
official installer asset, and starts that installer after the application
exits.  Portable builds never call this module.
"""

from __future__ import annotations

import json
import hashlib
import os
import re
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path


REPOSITORY = "Rhongomiant1227/CursorFence"
LATEST_RELEASE_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
DOWNLOAD_HOST_PREFIX = f"https://github.com/{REPOSITORY}/releases/download/"
DOWNLOAD_PATH_PREFIX = f"/{REPOSITORY}/releases/download/"
INSTALLER_ASSET_NAME = "CursorFence-Installer.exe"
MAX_DOWNLOAD_BYTES = 120 * 1024 * 1024
VERSION_PATTERN = re.compile(r"^[vV]?(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:[-+].*)?$")
SAFE_TAG_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True)
class ReleaseInfo:
    """The small subset of a GitHub release needed by the UI."""

    tag: str
    name: str
    url: str
    published_at: str = ""
    digest: str = ""


def version_tuple(value: str) -> tuple[int, int, int] | None:
    """Parse a release tag/version into a comparable numeric tuple."""
    match = VERSION_PATTERN.match(str(value).strip())
    if not match:
        return None
    return tuple(int(part or 0) for part in match.groups())


def is_newer_version(current: str, candidate: str) -> bool:
    """Return true only for a strictly newer semantic version."""
    current_version = version_tuple(current)
    candidate_version = version_tuple(candidate)
    return bool(current_version and candidate_version and candidate_version > current_version)


def _is_official_download_url(value: str) -> bool:
    """Accept only the canonical GitHub release asset URL."""
    try:
        parsed = urllib.parse.urlsplit(value)
    except ValueError:
        return False
    return (
        parsed.scheme.lower() == "https"
        and parsed.hostname == "github.com"
        and parsed.port is None
        and not parsed.username
        and not parsed.password
        and not parsed.query
        and not parsed.fragment
        and parsed.path.startswith(DOWNLOAD_PATH_PREFIX)
        and parsed.path.rsplit("/", 1)[-1] == INSTALLER_ASSET_NAME
    )


def fetch_latest_release(timeout: float = 5.0) -> ReleaseInfo | None:
    """Read the latest public release metadata from GitHub.

    Failures are intentionally converted to ``None``; update checks must never
    affect startup, hotkeys, or cursor locking when GitHub is unavailable.
    """
    request = urllib.request.Request(
        LATEST_RELEASE_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "CursorFence-updater",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(512 * 1024)
        payload = json.loads(raw.decode("utf-8"))
        tag = str(payload.get("tag_name", "")).strip()
        if not version_tuple(tag):
            return None
        assets = payload.get("assets", ())
        if not isinstance(assets, (list, tuple)):
            return None
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            if str(asset.get("name", "")) != INSTALLER_ASSET_NAME:
                continue
            url = str(asset.get("browser_download_url", "")).strip()
            if not _is_official_download_url(url):
                return None
            return ReleaseInfo(
                tag=tag,
                name=str(payload.get("name", "")).strip() or tag,
                url=url,
                published_at=str(payload.get("published_at", "")).strip(),
                digest=str(asset.get("digest", "")).strip(),
            )
    except (OSError, ValueError, TypeError, json.JSONDecodeError, urllib.error.URLError):
        return None
    return None


def cleanup_old_downloads() -> None:
    """Best-effort cleanup of installers left in the user's temp directory."""
    temp_dir = Path(tempfile.gettempdir())
    for path in temp_dir.glob("CursorFence-update-*.exe"):
        try:
            path.unlink()
        except OSError:
            # The previous installer may still be finishing; leave it alone.
            pass


def download_installer(release: ReleaseInfo, timeout: float = 30.0) -> Path:
    """Download an official installer asset to a temporary executable path."""
    if not _is_official_download_url(release.url):
        raise ValueError("installer URL is not an official CursorFence release asset")
    request = urllib.request.Request(
        release.url,
        headers={
            "Accept": "application/octet-stream",
            "User-Agent": "CursorFence-updater",
        },
    )
    # Release tags are server-provided text; keep path separators out of the
    # temporary filename prefix.
    safe_tag = SAFE_TAG_PATTERN.sub("-", str(release.tag)).strip(".-") or "release"
    file_handle, temporary_name = tempfile.mkstemp(prefix=f"CursorFence-update-{safe_tag}-", suffix=".exe")
    os.close(file_handle)
    target = Path(temporary_name)
    total = 0
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response, target.open("wb") as output:
            expected = int(response.headers.get("Content-Length", "0") or 0)
            if expected > MAX_DOWNLOAD_BYTES:
                raise ValueError("installer download is unexpectedly large")
            checksum = hashlib.sha256()
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_DOWNLOAD_BYTES:
                    raise ValueError("installer download is unexpectedly large")
                output.write(chunk)
                checksum.update(chunk)
            if expected and total != expected:
                raise OSError("installer download was truncated")
            if release.digest:
                digest = release.digest.removeprefix("sha256:").lower()
                if len(digest) != 64 or checksum.hexdigest().lower() != digest:
                    raise OSError("installer checksum verification failed")
        return target
    except Exception:
        try:
            target.unlink()
        except OSError:
            pass
        raise


def launch_installer(installer_path: Path) -> None:
    """Start Inno Setup silently, then let the caller close the app."""
    installer_path = installer_path.resolve()
    if os.name != "nt":
        raise OSError("CursorFence updates are supported on Windows only")
    startup_info = subprocess.STARTUPINFO()
    startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup_info.wShowWindow = 0
    subprocess.Popen(
        [
            str(installer_path),
            "/VERYSILENT",
            "/SUPPRESSMSGBOXES",
            "/NORESTART",
            "/CLOSEAPPLICATIONS",
        ],
        close_fds=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        startupinfo=startup_info,
    )
