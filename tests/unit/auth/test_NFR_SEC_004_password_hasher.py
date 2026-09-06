from __future__ import annotations

from pivot.security.passwords import Argon2idHasher, PasswordHasher


def test_NFR_SEC_004_password_hasher_protocol_is_one_way():
    assert hasattr(PasswordHasher, "hash")
    assert hasattr(PasswordHasher, "verify")


def test_NFR_SEC_004_argon2id_hasher_uses_expected_prefix():
    hasher = Argon2idHasher(time_cost=1, memory_cost=8, parallelism=1)
    digest = hasher.hash("CorrectHorseBattery")
    assert digest.startswith("$argon2id$")
    assert hasher.verify("CorrectHorseBattery", digest)
    assert not hasher.verify("wrong", digest)
    assert "CorrectHorseBattery" not in digest
