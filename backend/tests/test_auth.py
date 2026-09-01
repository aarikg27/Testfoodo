from app.auth import hash_password, hash_token, normalize_email, verify_password


def test_password_hashing_and_email_normalization():
    password_hash = hash_password("a-long-test-password")

    assert password_hash != "a-long-test-password"
    assert verify_password("a-long-test-password", password_hash)
    assert not verify_password("wrong-password", password_hash)
    assert normalize_email("  Student@UMD.EDU ") == "student@umd.edu"


def test_session_tokens_are_stored_as_fixed_hashes():
    token_hash = hash_token("a-random-session-token")
    assert len(token_hash) == 64
    assert token_hash != "a-random-session-token"

