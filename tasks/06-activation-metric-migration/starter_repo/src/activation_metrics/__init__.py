"""Starter package for the activation metric migration task."""

from .activation import compute_activation_rate_v1, compute_activation_rate_v2
from .report import build_activation_report

__all__ = [
    "__version__",
    "compute_activation_rate_v1",
    "compute_activation_rate_v2",
    "build_activation_report",
]

__version__ = "0.1.0"
