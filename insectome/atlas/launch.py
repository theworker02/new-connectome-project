"""Launch helpers for the local Insectome studio."""

from __future__ import annotations

import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from insectome.storage.paths import project_root


def frontend_dist() -> Path:
    return project_root() / "atlas" / "dist"


def frontend_ready() -> bool:
    d = frontend_dist()
    return d.exists() and (d / "index.html").exists()


def ensure_frontend_built(*, force: bool = False) -> Path:
    """Build atlas/dist if missing (requires Node/npm once)."""
    dist = frontend_dist()
    if frontend_ready() and not force:
        return dist

    atlas = project_root() / "atlas"
    npm = shutil.which("npm")
    if not npm:
        raise RuntimeError(
            "Studio UI not built and npm not found. Install Node.js, then: cd atlas && npm install && npm run build"
        )
    if not (atlas / "node_modules").exists():
        subprocess.run([npm, "install"], cwd=str(atlas), check=True)
    subprocess.run([npm, "run", "build"], cwd=str(atlas), check=True)
    if not frontend_ready():
        raise RuntimeError("npm run build finished but atlas/dist/index.html is missing")
    return dist


def api_healthy(host: str, port: int, timeout: float = 0.6) -> bool:
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/api/health", timeout=timeout) as r:
            return r.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def wait_healthy(host: str, port: int, seconds: float = 8.0) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        if api_healthy(host, port):
            return True
        time.sleep(0.25)
    return False


def studio_url(host: str, port: int, connectome_id: str | None = None) -> str:
    base = f"http://{host}:{port}"
    if not connectome_id:
        return base + "/"
    # Species key is only for routing; pack id is the source of truth
    return f"{base}/species/drosophila?c={connectome_id}"


def start_server_process(host: str, port: int):
    """Start uvicorn as a child process; return Popen."""
    import sys

    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    return subprocess.Popen(
        [
            sys.executable,
            "-c",
            "from insectome.atlas.api import run; run(host=%r, port=%d)" % (host, port),
        ],
        cwd=str(project_root()),
        env=env,
    )
