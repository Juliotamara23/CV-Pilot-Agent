"""Platform adapter discovery and lookup.

Adapters self-register at module import time via a module-level ``_register`` call.
The registry discovers all modules in the ``platforms/`` package, importing each
so they self-register. Malformed modules are skipped with a stderr warning.
"""

from __future__ import annotations

import sys
import pkgutil
from importlib import import_module
from pathlib import Path

from .base import PlatformAdapter

_registry: dict[str, type[PlatformAdapter]] = {}

def register(name: str, adapter_cls: type[PlatformAdapter]) -> None:
    if name in _registry:
        raise ValueError(f"Adapter '{name}' already registered")
    if not issubclass(adapter_cls, PlatformAdapter):
        raise TypeError(f"'{adapter_cls.__name__}' must subclass PlatformAdapter")
    _registry[name] = adapter_cls

def resolve(name: str) -> PlatformAdapter:
    cls = _registry.get(name)
    if cls is None:
        # Trigger discovery on first miss (covers late-loaded or partial scan)
        _discover()
        cls = _registry.get(name)
    if cls is None:
        available = ", ".join(sorted(_registry.keys())) or "none"
        raise SystemExit(
            f"Unknown platform '{name}'. Available: {available}"
        )
    return cls()

def list_platforms() -> list[str]:
    return sorted(_registry.keys())

def _discover() -> None:
    """Scan the platforms/ package for modules with registered adapters.
    Called eagerly at first resolve() call, or can be called explicitly."""
    for finder, name, _ispkg in pkgutil.iter_modules(
            [str(Path(__file__).parent)], prefix="platforms."):
        if name.endswith((".base", ".__init__", ".registry")):
            continue
        try:
            import_module(name)
        except Exception as exc:
            print(f"Warning: skipping platform module '{name}': {exc}",
                  file=sys.stderr)
