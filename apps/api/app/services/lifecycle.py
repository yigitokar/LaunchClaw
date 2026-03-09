from typing import Final


STATUS_ALIASES: Final[dict[str, str]] = {
    "healthy": "running",
    "running": "running",
    "degraded": "error",
    "failed": "error",
    "error": "error",
    "paused": "paused",
    "provisioning": "provisioning",
    "restarting": "restarting",
    "creating": "creating",
    "deleted": "deleted",
}

PERSISTED_STATUS_MAP: Final[dict[str, str]] = {
    "running": "healthy",
    "error": "failed",
    "paused": "paused",
    "provisioning": "provisioning",
    "restarting": "restarting",
    "creating": "creating",
    "deleted": "deleted",
}

ALLOWED_TRANSITIONS: Final[set[tuple[str, str]]] = {
    ("running", "paused"),
    ("paused", "provisioning"),
    ("running", "restarting"),
    ("error", "restarting"),
    ("error", "provisioning"),
    ("restarting", "running"),
    ("provisioning", "running"),
}


def normalize_status(status: str) -> str:
    return STATUS_ALIASES.get(status, status)


def to_persisted_status(status: str) -> str:
    normalized = normalize_status(status)
    return PERSISTED_STATUS_MAP.get(normalized, normalized)


def _status_label(raw_status: str, normalized_status: str) -> str:
    if raw_status == normalized_status:
        return raw_status
    return f"{raw_status} ({normalized_status})"


def validate_transition(current_status: str, target_status: str) -> str:
    normalized_current = normalize_status(current_status)
    normalized_target = normalize_status(target_status)

    if (normalized_current, normalized_target) in ALLOWED_TRANSITIONS:
        return to_persisted_status(normalized_target)

    current_label = _status_label(current_status, normalized_current)
    target_label = _status_label(target_status, normalized_target)
    allowed_targets = sorted(
        target for source, target in ALLOWED_TRANSITIONS if source == normalized_current
    )
    if allowed_targets:
        allowed_text = ", ".join(allowed_targets)
        raise ValueError(
            f"Cannot transition claw from {current_label} to {target_label}. "
            f"Allowed transitions from {normalized_current}: {allowed_text}."
        )

    raise ValueError(f"Cannot transition claw from {current_label} to {target_label}.")
