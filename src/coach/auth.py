import hmac


def check_bearer(authorization_header: str | None, *, expected: str) -> None:
    """Raise PermissionError if the header doesn't carry the expected bearer token."""
    if not authorization_header:
        raise PermissionError("missing Authorization header")
    parts = authorization_header.split(" ", 1)
    if len(parts) != 2 or parts[0] != "Bearer":
        raise PermissionError("invalid Authorization scheme")
    if not hmac.compare_digest(parts[1], expected):
        raise PermissionError("invalid bearer token")
