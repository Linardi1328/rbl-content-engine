"""Local contracts for RBL Topview discovery, validation, and preflight.

This package performs no network, MCP, generation, editing, or publishing calls.
"""

from .preflight import PreflightResult, evaluate_preflight
from .validator import (
    ValidationIssue,
    ValidationResult,
    load_json,
    validate_capabilities,
    validate_manifest,
    validate_state,
)

__all__ = [
    "PreflightResult",
    "ValidationIssue",
    "ValidationResult",
    "evaluate_preflight",
    "load_json",
    "validate_capabilities",
    "validate_manifest",
    "validate_state",
]
