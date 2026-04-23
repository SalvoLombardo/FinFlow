import pytest
from jose import JWTError

from app.services.auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_and_verify_correct_password():
    hashed = hash_password("mysecretpassword")
    assert verify_password("mysecretpassword", hashed)


def test_verify_wrong_password_returns_false():
    hashed = hash_password("mysecretpassword")
    assert not verify_password("wrongpassword", hashed)


def test_hash_produces_different_values_each_time():
    h1 = hash_password("same")
    h2 = hash_password("same")
    assert h1 != h2


def test_create_and_decode_access_token_roundtrip():
    subject = "550e8400-e29b-41d4-a716-446655440000"
    token = create_access_token(subject)
    assert decode_access_token(token) == subject


def test_decode_garbage_token_raises():
    with pytest.raises(Exception):
        decode_access_token("not.a.valid.token")


def test_decode_tampered_token_raises():
    token = create_access_token("user-id")
    tampered = token[:-4] + "xxxx"
    with pytest.raises(Exception):
        decode_access_token(tampered)
