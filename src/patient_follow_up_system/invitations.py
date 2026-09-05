import hashlib
import io
import secrets
from datetime import UTC, datetime
from enum import StrEnum

from pwdlib import PasswordHash
import segno

from patient_follow_up_system.models import PatientInvitation


INVITATION_TOKEN_BYTES = 32
VERIFICATION_CODE_LENGTH = 6
VERIFICATION_CODE_ALPHABET = "0123456789"
MAX_FAILED_VERIFICATION_ATTEMPTS = 5

verification_code_hash = PasswordHash.recommended()


class InvitationState(StrEnum):
    AVAILABLE = "available"
    EXPIRED = "expired"
    REVOKED = "revoked"
    EXHAUSTED = "exhausted"
    LOCKED = "locked"
    UNAVAILABLE = "unavailable"


def generate_invitation_token() -> str:
    return secrets.token_urlsafe(INVITATION_TOKEN_BYTES)


def digest_invitation_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def invitation_qr_svg(invitation_url: str) -> str:
    output = io.BytesIO()
    segno.make(invitation_url, error="m").save(
        output,
        kind="svg",
        scale=5,
        border=2,
        dark="#123c69",
    )
    return output.getvalue().decode("utf-8")


def generate_verification_code() -> str:
    return "".join(
        secrets.choice(VERIFICATION_CODE_ALPHABET)
        for _ in range(VERIFICATION_CODE_LENGTH)
    )


def hash_verification_code(code: str) -> str:
    return verification_code_hash.hash(code)


def verify_verification_code(code: str, code_hash: str) -> bool:
    return verification_code_hash.verify(code, code_hash)


def utc_for_comparison(value: datetime | None = None) -> datetime:
    current = value or datetime.now(UTC)
    if current.tzinfo is None:
        return current
    return current.astimezone(UTC).replace(tzinfo=None)


def invitation_state(
    invitation: PatientInvitation,
    now: datetime | None = None,
) -> InvitationState:
    current = utc_for_comparison(now)
    if invitation.revoked_at is not None:
        return InvitationState.REVOKED
    if invitation.locked_at is not None:
        return InvitationState.LOCKED
    if invitation.expires_at <= current:
        return InvitationState.EXPIRED
    if invitation.used_count >= invitation.max_uses:
        return InvitationState.EXHAUSTED
    return InvitationState.AVAILABLE
