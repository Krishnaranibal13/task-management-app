"""Argon2id password hashing tests (unit, no DB)."""

from app.auth.security import (
    DUMMY_HASH,
    hash_password,
    verify_dummy_for_unknown_email,
    verify_password,
)


def test_hash_differs_from_plaintext() -> None:
    plaintext = "correct horse battery staple"
    h = hash_password(plaintext)
    assert h != plaintext
    assert plaintext not in h


def test_correct_password_verifies() -> None:
    h = hash_password("s3cret-value")
    assert verify_password("s3cret-value", h) is True


def test_incorrect_password_rejected() -> None:
    h = hash_password("s3cret-value")
    assert verify_password("wrong", h) is False


def test_hashes_are_salted_and_unique() -> None:
    assert hash_password("same-input") != hash_password("same-input")


def test_dummy_hash_is_usable_for_verification_work() -> None:
    # Must not raise; performs real Argon2id verification work.
    assert verify_password("whatever", DUMMY_HASH) is False
    verify_dummy_for_unknown_email("some-guess")


def test_malformed_hash_rejected_cleanly() -> None:
    assert verify_password("x", "not-a-hash") is False
