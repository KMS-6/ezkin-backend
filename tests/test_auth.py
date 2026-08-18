import base64
import uuid

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.core import auth

_BASE64URL_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"


def test_decode_round_trips_canonical_encoding() -> None:
    assert auth._decode(auth._encode(b"a 32-byte-ish sample payload!!!")) == (
        b"a 32-byte-ish sample payload!!!"
    )


def test_decode_rejects_non_canonical_padding_bits() -> None:
    # A 32-byte value (matching a real HMAC-SHA256 digest) base64-encodes to a
    # final character whose low bits are unused padding. A non-validating
    # decoder ignores those bits, so a different last character can decode to
    # the exact same bytes — `_decode` must reject that as tampering.
    canonical = auth._encode(b"\x01" * 32)
    canonical_bytes = base64.urlsafe_b64decode(canonical + "=" * (-len(canonical) % 4))
    prefix, last_char = canonical[:-1], canonical[-1]

    same_bytes_variant = None
    for candidate in _BASE64URL_ALPHABET:
        if candidate == last_char:
            continue
        candidate_token = prefix + candidate
        padded = candidate_token + "=" * (-len(candidate_token) % 4)
        if base64.urlsafe_b64decode(padded) == canonical_bytes:
            same_bytes_variant = candidate_token
            break

    assert same_bytes_variant is not None, "expected a same-bytes non-canonical variant to exist"
    assert auth._decode(canonical) == canonical_bytes
    with pytest.raises(ValueError):
        auth._decode(same_bytes_variant)


async def test_every_single_character_tamper_of_a_token_is_rejected() -> None:
    # Regression test for the flaky tamper-detection behavior in
    # test_shelf_api.py: flipping the token's last character used to have
    # roughly a 1-in-16 chance of decoding to the same signature bytes and
    # being wrongly accepted. Two layers now cooperate to reject every
    # variant: `_decode` rejects same-bytes non-canonical re-encodings, and
    # the HMAC comparison rejects variants that decode to different bytes.
    token = auth.create_access_token(uuid.uuid4())
    prefix, last_char = token[:-1], token[-1]

    for candidate in _BASE64URL_ALPHABET:
        if candidate == last_char:
            continue
        tampered = prefix + candidate
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=tampered)
        with pytest.raises(HTTPException) as exc_info:
            await auth.get_current_user_id(credentials)
        assert exc_info.value.status_code == 401
