"""Pytest shared fixtures / environment workarounds.

Windows WMI workaround: SQLAlchemy calls platform.uname() at import, which on
Windows triggers a WMI query that can hang under system load (or when the WMI
service is slow). We cache a fast uname result so every test that imports
SQLAlchemy (db models, task queue, agents, ...) does not block on WMI.
"""
from __future__ import annotations

import os
import platform

if os.name == "nt":
    _machine = os.environ.get("PROCESSOR_ARCHITECTURE", "AMD64")
    _cached_uname = platform.uname_result("Windows", "localhost", "10", "10.0.0", _machine)
    platform.uname = lambda: _cached_uname  # type: ignore[method-assign]
