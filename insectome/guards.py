"""Download and compute guards — no silent multi-GB transfers."""

from __future__ import annotations

from dataclasses import dataclass


class DownloadGuardError(RuntimeError):
    pass


class ComputeGuardError(RuntimeError):
    pass


@dataclass
class DownloadEstimate:
    operation: str
    expected_download_bytes: int
    expected_temporary_bytes: int
    expected_final_bytes: int
    estimated_runtime_sec: float | None = None
    notes: str = ""

    @property
    def expected_download_gb(self) -> float:
        return self.expected_download_bytes / (1024**3)


@dataclass
class ComputeEstimate:
    operation: str
    gpu_hours: float | None
    cpu_hours: float | None
    network_transfer_bytes: int
    temporary_disk_bytes: int
    final_disk_bytes: int
    notes: str = ""


WARN_BYTES = 1 * 1024**3  # 1 GB
REQUIRE_AUTH_BYTES = 10 * 1024**3  # 10 GB
DEFAULT_COMPUTE_THRESHOLD_CPU_HOURS = 4.0


def format_bytes(n: int) -> str:
    for unit, div in (("GB", 1024**3), ("MB", 1024**2), ("KB", 1024)):
        if n >= div:
            return f"{n / div:.2f} {unit}"
    return f"{n} B"


def check_download(estimate: DownloadEstimate, *, authorize: bool = False) -> None:
    """Raise unless download is allowed. >10 GB requires authorize=True."""
    msg = (
        f"Download guard for '{estimate.operation}':\n"
        f"  expected download : {format_bytes(estimate.expected_download_bytes)}\n"
        f"  temporary storage : {format_bytes(estimate.expected_temporary_bytes)}\n"
        f"  final storage     : {format_bytes(estimate.expected_final_bytes)}\n"
        f"  runtime           : {estimate.estimated_runtime_sec}\n"
        f"  notes             : {estimate.notes}"
    )
    if estimate.expected_download_bytes > REQUIRE_AUTH_BYTES and not authorize:
        raise DownloadGuardError(
            msg + "\nRefused: >10 GB requires explicit authorize=True / --authorize-download."
        )
    if estimate.expected_download_bytes > WARN_BYTES:
        # Still allowed under 10 GB, but caller should surface the estimate.
        estimate.notes = (estimate.notes + " | WARNING: >1 GB").strip(" |")


def check_compute(
    estimate: ComputeEstimate,
    *,
    authorize: bool = False,
    cpu_hour_threshold: float = DEFAULT_COMPUTE_THRESHOLD_CPU_HOURS,
) -> None:
    cpu = estimate.cpu_hours or 0.0
    gpu = estimate.gpu_hours or 0.0
    if (cpu > cpu_hour_threshold or gpu > cpu_hour_threshold) and not authorize:
        raise ComputeGuardError(
            f"Compute guard for '{estimate.operation}': "
            f"cpu_hours={cpu}, gpu_hours={gpu} exceeds threshold={cpu_hour_threshold}. "
            f"Search for reusable upstream products before authorizing. notes={estimate.notes}"
        )
