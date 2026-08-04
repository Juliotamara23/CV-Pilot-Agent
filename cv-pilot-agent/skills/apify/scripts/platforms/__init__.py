"""Platform adapters for the `search_jobs.py` dispatcher.

Provides access to concrete adapter classes and the plugin discovery registry.
Adapters auto-register when imported.
"""

from .base import PlatformAdapter
from .registry import register, resolve, list_platforms, _discover

# Legacy exports for tests and external imports that reference adapter classes
from .computrabajo import ComputrabajoAdapter
from .indeed import IndeedAdapter
from .linkedin import LinkedinAdapter

__all__ = [
    "PlatformAdapter",
    "register",
    "resolve",
    "list_platforms",
    "_discover",
    "ComputrabajoAdapter",
    "IndeedAdapter",
    "LinkedinAdapter",
]