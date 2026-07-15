"""Error hierarchy for CV-Pilot.

All errors inherit from :class:`CV_PilotError`. Each subclass carries a default
``code`` string used by the CLI's stderr envelope::

    {"ok": false, "error": "...", "code": "..."}

The ``code`` keyword argument lets callers reuse a single exception class for
semantically distinct not-found situations (job not found vs. analysis not
found vs. no jobs matched by a delete filter) without inventing extra classes.
"""


class CV_PilotError(Exception):
    """Base error for every CV-Pilot failure."""

    code = "CV_PILOT_ERROR"

    def __init__(self, message: str = "", *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code

    @property
    def message(self) -> str:
        return self.args[0] if self.args else ""


class DatabaseError(CV_PilotError):
    """Unexpected SQLite / filesystem failure."""

    code = "DATABASE_ERROR"


class JobNotFoundError(CV_PilotError):
    """A job lookup returned no row. Code is overridable for delete filters."""

    code = "JOB_NOT_FOUND"


class DuplicateJobError(CV_PilotError):
    """Raised when a hard duplicate is forced instead of dedup-ignored."""

    code = "DUPLICATE_JOB"


class ValidationError(CV_PilotError):
    """Domain-level validation failure (bad status, bad input, etc.)."""

    code = "VALIDATION_ERROR"