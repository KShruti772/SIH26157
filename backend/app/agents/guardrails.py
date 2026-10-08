"""
Output validation, evidence grounding guardrails, and anti-hallucination checks.

Enforces:
1. Strict JSON schema compliance.
2. Evidence ID existence checks (all cited IDs must exist in the bounded context).
3. Entity ID and Finding ID consistency.
4. Rejection or repair of hallucinated identifiers.
"""

from typing import List, Dict, Any, Tuple, Type, TypeVar
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class GuardrailValidationError(ValueError):
    """Raised when an agent output fails critical guardrail validation."""
    pass


def validate_and_filter_evidence_ids(
    cited_ids: List[str],
    valid_ids: List[str],
    allow_blindspot_tokens: bool = True,
) -> Tuple[List[str], List[str]]:
    """
    Validate cited evidence IDs against the canonical list of valid evidence IDs in context.
    Returns:
        (sanitized_valid_ids, invalid_or_hallucinated_ids)
    """
    valid_set = set(valid_ids)
    sanitized: List[str] = []
    invalid: List[str] = []

    for eid in cited_ids:
        if not eid:
            continue
        cleaned = str(eid).strip()
        # Accept valid evidence ID or standardized assurance tokens like BLINDSPOT_*
        if cleaned in valid_set:
            if cleaned not in sanitized:
                sanitized.append(cleaned)
        elif allow_blindspot_tokens and cleaned.startswith("BLINDSPOT_"):
            if cleaned not in sanitized:
                sanitized.append(cleaned)
        else:
            invalid.append(cleaned)

    return sanitized, invalid


def validate_schema_output(
    data: Dict[str, Any],
    schema_cls: Type[T],
    valid_evidence_ids: List[str],
) -> Tuple[T, str]:
    """
    Validate dictionary against Pydantic schema and enforce evidence grounding guardrails.
    Returns:
        (validated_instance, validation_status: "PASSED" | "REPAIRED")
    Raises:
        GuardrailValidationError if parsing or validation fails unrecoverably.
    """
    try:
        instance = schema_cls.model_validate(data)
    except ValidationError as ve:
        raise GuardrailValidationError(f"Schema validation failed for {schema_cls.__name__}: {str(ve)}")

    validation_status = "PASSED"

    # Enforce evidence grounding across schema fields
    if hasattr(instance, "supporting_evidence"):
        valid_refs, invalid_refs = validate_and_filter_evidence_ids(
            instance.supporting_evidence, valid_evidence_ids
        )
        if invalid_refs:
            validation_status = "REPAIRED"
            instance.supporting_evidence = valid_refs

    if hasattr(instance, "counter_evidence"):
        valid_refs, invalid_refs = validate_and_filter_evidence_ids(
            instance.counter_evidence, valid_evidence_ids
        )
        if invalid_refs:
            validation_status = "REPAIRED"
            instance.counter_evidence = valid_refs

    if hasattr(instance, "reasoning") and isinstance(instance.reasoning, list):
        for step in instance.reasoning:
            if hasattr(step, "evidence_ids") and step.evidence_ids:
                v_ids, inv_ids = validate_and_filter_evidence_ids(step.evidence_ids, valid_evidence_ids)
                if inv_ids:
                    validation_status = "REPAIRED"
                    step.evidence_ids = v_ids

    return instance, validation_status
