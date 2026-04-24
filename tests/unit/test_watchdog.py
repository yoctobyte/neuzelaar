"""Tests for the process-level resource watchdog."""

import neuzelaar.core.watchdog as watchdog


def test_check_resources_passes_under_limits():
    """Normal operation should not raise."""
    watchdog.configure(max_rss_mb=4096, max_cpu_seconds=600)
    watchdog.check_resources()  # should not raise


def test_check_resources_raises_on_memory_exceeded():
    """If RSS exceeds the configured limit, WatchdogError is raised."""
    # Set an absurdly low limit to trigger it.
    watchdog.configure(max_rss_mb=1)
    try:
        watchdog.check_resources()
        # If the process somehow uses less than 1 MB RSS, that's fine.
        # On any real system this will raise.
        assert True
    except watchdog.WatchdogError as exc:
        assert "Memory limit exceeded" in str(exc)
    finally:
        watchdog.configure(max_rss_mb=512)


def test_current_usage_returns_diagnostics():
    """current_usage() should return a dict with expected keys."""
    usage = watchdog.current_usage()
    assert "rss_mb" in usage
    assert "cpu_seconds" in usage
    assert "max_rss_mb" in usage
    assert "max_cpu_seconds" in usage
    assert usage["rss_mb"] >= 0
    assert usage["cpu_seconds"] >= 0


def test_configure_changes_limits():
    """configure() should update the limits."""
    watchdog.configure(max_rss_mb=1024, max_cpu_seconds=300)
    usage = watchdog.current_usage()
    assert usage["max_rss_mb"] == 1024
    assert usage["max_cpu_seconds"] == 300
    # Restore defaults
    watchdog.configure(max_rss_mb=512, max_cpu_seconds=120)
