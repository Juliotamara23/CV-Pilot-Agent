"""Platform adapters for the `search_jobs.py` dispatcher.

Re-exports the concrete adapters so the dispatcher can resolve a platform by
name without importing each module eagerly elsewhere::

    from platforms import ADAPTERS, LinkedinAdapter
"""

from .computrabajo import ComputrabajoAdapter
from .indeed import IndeedAdapter
from .linkedin import LinkedinAdapter

__all__ = ["IndeedAdapter", "LinkedinAdapter", "ComputrabajoAdapter"]