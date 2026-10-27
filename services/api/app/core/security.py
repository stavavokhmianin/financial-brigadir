import hashlib
import secrets


def new_session_token() -> str:
    """32 байта энтропии; клиенту отдаётся только один раз."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
