from admin_session import create_admin_token, derive_signing_key, verify_admin_token


def test_admin_token_is_valid_for_matching_user_and_secrets():
    key = derive_signing_key("cookie-secret", "admin-password")
    token = create_admin_token("user@example.com", key)

    assert verify_admin_token(token, "user@example.com", key)


def test_admin_token_is_rejected_for_another_user_or_secret():
    key = derive_signing_key("cookie-secret", "admin-password")
    token = create_admin_token("user@example.com", key)

    assert not verify_admin_token(token, "other@example.com", key)
    assert not verify_admin_token(token, "user@example.com", derive_signing_key("other", "admin-password"))


def test_tampered_admin_token_is_rejected():
    key = derive_signing_key("cookie-secret", "admin-password")
    token = create_admin_token("user@example.com", key)
    payload, signature = token.rsplit(".", 1)
    replacement = "0" if signature[-1] != "0" else "1"

    assert not verify_admin_token(f"{payload}.{signature[:-1]}{replacement}", "user@example.com", key)
    assert not verify_admin_token("not-a-token", "user@example.com", key)
