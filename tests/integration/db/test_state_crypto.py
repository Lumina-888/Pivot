"""Tests for the checkpoint state encryption seam (04-C task 2.3).

Placeholder scope: only the ``none`` scheme exists until the OpenBao
key policy is approved. Unknown schemes must fail closed rather than
pass a foreign payload through as plaintext.
"""

import pytest

from pivot.agent.state_crypto import StateCipher, StateCryptoError


def test_FR_AGENT_006_state_cipher_roundtrip_preserves_state():
    cipher = StateCipher()
    state = {"messages": [{"role": "user", "content": "hi"}], "steps_taken": 2}

    envelope = cipher.encrypt(state)

    assert envelope["encryption"] == "none"
    assert cipher.decrypt(envelope) == state


def test_FR_AGENT_006_state_cipher_rejects_unknown_scheme():
    cipher = StateCipher()

    with pytest.raises(StateCryptoError):
        cipher.decrypt({"encryption": "openbao-v1", "state": {}})


def test_FR_AGENT_006_state_cipher_rejects_malformed_envelope():
    cipher = StateCipher()

    with pytest.raises(StateCryptoError):
        cipher.decrypt({"encryption": "none"})
