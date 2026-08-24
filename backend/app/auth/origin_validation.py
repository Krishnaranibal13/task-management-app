"""Centralized Origin/Referer defense-in-depth (SEC-MED-01).

Approved CSRF architecture: the session-bound synchronizer token is the
PRIMARY control; Origin/Referer validation is ADDITIONAL defense-in-depth
for authenticated state-changing requests. It never replaces or weakens
the synchronizer-token check.

Policy implemented here (fail-closed):

  - POST / PUT / PATCH / DELETE only; safe methods are unaffected.
  - If ``Origin`` is present it must belong to the trusted-origin set.
  - Else if ``Referer`` is present, its ORIGIN component (scheme + host +
    effective port) must belong to the trusted set. Only the origin of
    the Referer URL is compared; the full URL is never stored, echoed,
    or logged.
  - If neither header is present the request proceeds: browsers omit both
    on same-origin requests, so absence is not an attack signal — and the
    primary synchronizer-token check still fully applies.
  - Trusted origins come from the SAME authoritative allowlist used for
    CORS configuration (``CORS_ALLOWED_ORIGINS_RAW``); there is no second
    source of truth.

Matching is EXACT equality on normalized origins (lowercased scheme and
host + effective port, scheme-default ports elided). No wildcards, no
credentialed '*', no substring matching, no suffix matching, no regex —
attacker-controlled look-alike hosts cannot slip through.

When NO trusted origin is configured (the approved same-origin production
posture), the request's own strictly validated ``Host`` header defines the
single acceptable self-origin, so zero-configuration local/same-origin and
test behavior keeps working while every foreign origin fails closed. The
Host value is parsed under a strict authority grammar before use; it is
never concatenated unchecked into a comparison string.
"""

from urllib.parse import urlsplit

from fastapi import HTTPException, Request, status

from app.core.config import settings

# Methods guarded by this layer. Safe methods (GET/HEAD/OPTIONS) are
# deliberately excluded.
_PROTECTED_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

_WEB_SCHEMES = frozenset({"http", "https", "ws", "wss"})


class UntrustedPresentationError(Exception):
    """A presented Origin/Referer/Host value cannot be parsed as a clean
    web origin. Internal only; callers convert this into HTTP 403."""


def _reject() -> HTTPException:
    """Generic 403 — never reflects the offending header value."""
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


# --- normalization ----------------------------------------------------------


def _default_port_for(scheme: str) -> int | None:
    return {
        "http": 80,
        "https": 443,
        "ws": 80,
        "wss": 443,
    }.get(scheme)


def _authority_of(netloc: str) -> tuple[str, int | None]:
    """Split a URL authority into ``(lowercased_host, explicit_port)``.

    Rejects userinfo (``user:pass@host``) — legitimate Origin values and
    configured origins never carry credentials.
    """
    if "@" in netloc:
        raise UntrustedPresentationError("userinfo in authority")
    parsed = urlsplit(f"//{netloc}")
    host = parsed.hostname
    if not host:
        raise UntrustedPresentationError("missing hostname")
    try:
        port = parsed.port  # raises ValueError on malformed ports
    except ValueError:
        raise UntrustedPresentationError("malformed port")
    return host.lower(), port


def _canonical_origin(scheme: str, host: str, port: int | None) -> str:
    """Serialize ``scheme://host[:port]`` with default-port elision."""
    if port is not None and port != _default_port_for(scheme):
        return f"{scheme}://{host}:{port}"
    return f"{scheme}://{host}"


def _normalize_pure_origin(raw: str) -> str:
    """Normalize a PURE origin string (exactly what ``Origin`` carries).

    Anything beyond scheme + authority (path, query, fragment), any
    non-web scheme, embedded credentials, whitespace, comma-lists, or a
    malformed port makes the value untrusted.
    """
    candidate = (raw or "").strip()
    if not candidate or candidate.casefold() == "null":
        # Opaque 'null' origin (sandboxed frames, certain redirects) is
        # never trustable.
        raise UntrustedPresentationError("opaque or empty origin")
    if "," in candidate or any(c.isspace() for c in candidate):
        raise UntrustedPresentationError("malformed origin syntax")
    parts = urlsplit(candidate)
    scheme = parts.scheme.lower()
    if scheme not in _WEB_SCHEMES:
        raise UntrustedPresentationError("unsupported scheme")
    if parts.path not in ("", "/") or parts.query or parts.fragment:
        # An Origin is a bare origin; anything attached is malformed.
        raise UntrustedPresentationError("unexpected components in origin")
    host, port = _authority_of(parts.netloc)
    return _canonical_origin(scheme, host, port)


def _origin_of_referer(raw: str) -> str:
    """Extract ONLY the origin of a ``Referer`` URL, then normalize it.

    Path and query are discarded before comparison; the full URL never
    leaves this function and is never logged.
    """
    candidate = (raw or "").strip()
    if not candidate:
        raise UntrustedPresentationError("empty Referer")
    parts = urlsplit(candidate)
    scheme = parts.scheme.lower()
    if scheme not in _WEB_SCHEMES or not parts.netloc:
        raise UntrustedPresentationError("unusable Referer")
    host, port = _authority_of(parts.netloc)
    return _canonical_origin(scheme, host, port)


def _normalized_self_authority(host_header: str) -> str:
    """Validate a raw ``Host`` header; return ``host[:port]`` authority.

    Strict RFC 9110 authority grammar only: ``host`` optionally followed
    by ``:`` and digits-only port (bracket-wrapped IPv6 supported).
    Paths, queries, fragments, userinfo, spaces, control characters and
    ambiguous bare-IPv6 forms are rejected, so attacker-controlled text
    can never be concatenated into the trusted self-origin string.
    """
    raw = (host_header or "").strip()
    if not raw:
        raise UntrustedPresentationError("missing Host")
    if any(c in raw for c in ("/", "?", "#", "@")) or any(
        c.isspace() or ord(c) < 0x21 for c in raw
    ):
        raise UntrustedPresentationError("illegal characters in Host")

    if raw.startswith("["):  # bracketed IPv6 literal
        closing = raw.find("]")
        if closing == -1:
            raise UntrustedPresentationError("unterminated IPv6 literal")
        host = raw[1:closing].lower()
        rest = raw[closing + 1:]
        if not host:
            raise UntrustedPresentationError("empty IPv6 literal")
        if not rest:  # e.g. "[::1]"
            return host
        if not rest.startswith(":") or not rest[1:].isdigit():
            raise UntrustedPresentationError("invalid IPv6 Host port")
        port = int(rest[1:])
        if not (0 < port <= 65535):
            raise UntrustedPresentationError("out-of-range IPv6 Host port")
        if port in (80, 443):
            return host  # transport-default port elides
        return f"[{host}]:{port}"

    host, sep, port_text = raw.rpartition(":")
    if not sep:
        return raw.lower()
    if not port_text.isdigit():
        raise UntrustedPresentationError("non-numeric Host port")
    port = int(port_text)
    if not (0 < port <= 65535):
        raise UntrustedPresentationError("out-of-range Host port")
    if ":" in host:  # bare (unbracketed) IPv6 — ambiguous, reject
        raise UntrustedPresentationError("ambiguous bare IPv6 Host")
    if port in (80, 443):
        return host.lower()  # transport-default port elides
    return f"{host.lower()}:{port}"


# --- trust set ---------------------------------------------------------------


def trusted_origin_set() -> frozenset[str]:
    """Normalized trusted origins from the SINGLE authoritative CORS list.

    A wildcard can never survive here: ``*`` is not an absolute web URL
    and is additionally rejected at application startup by the CORS
    wiring. Entries that do not parse as clean origins are dropped rather
    than partially trusted (a mis-declared allowlist is a deployment
    configuration error, surfaced by review, not by silent acceptance).
    """
    configured = settings.cors_allowed_origins
    if not configured:
        return frozenset()
    trusted: set[str] = set()
    for entry in configured:
        try:
            trusted.add(_normalize_pure_origin(entry))
        except UntrustedPresentationError:
            continue
    return frozenset(trusted)


def _self_origin(request: Request) -> str:
    """The only acceptable origin when NO allowlist is configured: the
    request's own validated Host (transport assumed plain HTTP; TLS-
    terminating deployments must configure the explicit allowlist, which
    is the approved production posture)."""
    return f"http://{_normalized_self_authority(request.headers.get('Host', ''))}"


# --- public gate --------------------------------------------------------------


def validate_request_origin(request: Request) -> None:
    """Defense-in-depth gate for authenticated state-changing requests.

    Raises HTTP 403 with a generic body when a PRESENTED Origin/Referer
    does not match the trusted-origin set (or, absent configuration, the
    request's own validated Host). Header values are never reflected in
    errors and full Referer URLs are never logged.
    """
    if request.method.upper() not in _PROTECTED_METHODS:
        return

    origin = request.headers.get("Origin")
    referer = request.headers.get("Referer")

    if origin:
        presented = _presented_origin_of(_normalize_pure_origin, origin)
    elif referer:
        presented = _presented_origin_of(_origin_of_referer, referer)
    else:
        # Both absent: same-origin user agents commonly omit them, so
        # absence is not an attack signal. The session-bound synchronizer
        # token remains the PRIMARY control on this request.
        return

    trusted = trusted_origin_set()
    if trusted:
        if presented in trusted:
            return
        raise _reject()

    # Same-origin fallback posture (no usable configured allowlist):
    # accept only the request's own strictly validated Host. Invalid
    # Host → fail closed with the SAME generic 403.
    try:
        allowed_here = presented == _self_origin(request)
    except UntrustedPresentationError:
        allowed_here = False
    if not allowed_here:
        raise _reject()


def _presented_origin_of(normalizer, raw: str) -> str:
    """Normalize a presented header value; malformed → generic 403."""
    try:
        return normalizer(raw)
    except UntrustedPresentationError:
        raise _reject()
