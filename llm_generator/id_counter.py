"""
Global ID counter for constraint generation.
Provides timestamp-based sequential IDs that are unique across different runs.
"""

import time

_counter = 0
_run_timestamp = None

def _get_run_timestamp():
    """Get the timestamp for the current run."""
    global _run_timestamp
    if _run_timestamp is None:
        _run_timestamp = int(time.time())
    return _run_timestamp

def get_next_id() -> str:
    """Get the next sequential ID with timestamp prefix."""
    global _counter
    _counter += 1
    timestamp = _get_run_timestamp()
    return f"{timestamp}-{_counter}"

def reset_counter() -> None:
    """Reset the counter to 0 and start a new run timestamp."""
    global _counter, _run_timestamp
    _counter = 0
    _run_timestamp = None

def get_current_count() -> int:
    """Get the current counter value without incrementing."""
    return _counter
