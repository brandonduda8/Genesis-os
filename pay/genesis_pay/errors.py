"""Fail-closed error types for Genesis Pay S0.

Every error carries an HTTP-equivalent ``status`` so a future HTTP adapter
(Hyperswitch-era or otherwise) can map it 1:1 without re-classifying.
Unknown / unsafe states raise; nothing in this package guesses.
"""


class PayError(Exception):
    status = 400

    def __init__(self, message, status=None):
        super().__init__(message)
        if status is not None:
            self.status = status


class ValidationError(PayError):
    status = 400


class NotFoundError(PayError):
    status = 404


class ConflictError(PayError):
    """Same idempotency key, different payload (I-3: hard 409)."""

    status = 409


class StateError(PayError):
    """Illegal / backward state-machine transition."""

    status = 409


class GateError(PayError):
    """C8 approval-gate rejection (wrong actor, self-approval, expired...)."""

    status = 403


class SignatureError(PayError):
    status = 401


class CapExceededError(PayError):
    """Refund cap (I-17) or dispute-freeze cap would be exceeded."""

    status = 422
