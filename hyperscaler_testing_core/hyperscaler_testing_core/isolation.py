"""Test isolation helpers."""

from __future__ import annotations

import re
from uuid import uuid4


def unique_test_name(prefix: str, *, max_length: int = 63) -> str:
    """Create a libvirt-safe unique name for a test resource."""

    clean_prefix = re.sub(r"[^a-zA-Z0-9_.-]+", "-", prefix).strip("-")
    suffix = uuid4().hex[:12]
    available_prefix_length = max(1, max_length - len(suffix) - 1)
    return f"{clean_prefix[:available_prefix_length]}-{suffix}"
