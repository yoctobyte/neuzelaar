"""Process-level resource watchdog.

A simple safeguard that checks process memory (RSS) and cumulative CPU
time before expensive operations. If either exceeds a configured
threshold, a WatchdogError is raised to halt rendering gracefully
instead of crashing the X server or locking the system.

Usage:
    from neuzelaar.core.watchdog import check_resources

    check_resources()  # raises WatchdogError if limits exceeded
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass


class WatchdogError(RuntimeError):
    """Raised when the process exceeds resource safety limits."""


@dataclass(frozen=True, slots=True)
class ResourceLimits:
    max_rss_mb: int = 512          # Max resident set size in MB
    max_cpu_seconds: float = 120.0  # Max cumulative CPU time in seconds


_limits = ResourceLimits()
_start_cpu = time.process_time()


def configure(*, max_rss_mb: int | None = None, max_cpu_seconds: float | None = None) -> None:
    """Override the default resource limits."""
    global _limits
    _limits = ResourceLimits(
        max_rss_mb=max_rss_mb if max_rss_mb is not None else _limits.max_rss_mb,
        max_cpu_seconds=max_cpu_seconds if max_cpu_seconds is not None else _limits.max_cpu_seconds,
    )


def check_resources() -> None:
    """Check current process resource usage and raise if limits are exceeded."""
    rss_mb = _get_rss_mb()
    if rss_mb > _limits.max_rss_mb:
        raise WatchdogError(
            f"Memory limit exceeded: {rss_mb:.0f} MB RSS > {_limits.max_rss_mb} MB limit. "
            f"Halting to prevent system instability."
        )

    cpu_elapsed = time.process_time() - _start_cpu
    if cpu_elapsed > _limits.max_cpu_seconds:
        raise WatchdogError(
            f"CPU time limit exceeded: {cpu_elapsed:.1f}s > {_limits.max_cpu_seconds:.1f}s limit. "
            f"Halting to prevent system lockup."
        )


def current_usage() -> dict[str, float]:
    """Return current resource usage for diagnostics."""
    return {
        "rss_mb": _get_rss_mb(),
        "cpu_seconds": time.process_time() - _start_cpu,
        "max_rss_mb": _limits.max_rss_mb,
        "max_cpu_seconds": _limits.max_cpu_seconds,
    }


def _get_rss_mb() -> float:
    """Get current process RSS in megabytes."""
    try:
        # Linux: read from /proc/self/status (most reliable)
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    # Value is in kB
                    return int(line.split()[1]) / 1024.0
    except (OSError, ValueError, IndexError):
        pass

    try:
        # Fallback: use resource module (works on macOS too)
        import resource
        usage = resource.getrusage(resource.RUSAGE_SELF)
        # ru_maxrss is in KB on Linux, bytes on macOS
        if os.uname().sysname == "Darwin":
            return usage.ru_maxrss / (1024 * 1024)
        return usage.ru_maxrss / 1024
    except (ImportError, AttributeError):
        pass

    return 0.0  # Unknown platform — don't block
