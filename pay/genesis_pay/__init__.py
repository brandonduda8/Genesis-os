"""Genesis Pay S0 — owned double-entry ledger, payment intents, C8 tap gate,
webhook ingestor and three-way reconciliation on today's Apex/manual rails.

Stdlib only. No money ever moves from this package: there is deliberately
no send/execute adapter. Outbound movements are Brandon tap requests that,
once approved, yield a *prepared instruction only* (see README, C8 / I-18..I-20).
"""

from .core import GenesisPay
from .paylinks import build_rails, load_config, qr_svg, render_pay_page
from .errors import (
    CapExceededError,
    ConflictError,
    GateError,
    NotFoundError,
    PayError,
    SignatureError,
    StateError,
    ValidationError,
)

__all__ = [
    "GenesisPay",
    "build_rails",
    "load_config",
    "qr_svg",
    "render_pay_page",
    "PayError",
    "ValidationError",
    "NotFoundError",
    "ConflictError",
    "StateError",
    "GateError",
    "SignatureError",
    "CapExceededError",
]
__version__ = "0.2.0"
