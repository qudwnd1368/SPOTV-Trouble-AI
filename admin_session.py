import base64
import hashlib
import hmac


def derive_signing_key(cookie_secret, admin_password):
    material = f"{cookie_secret}\0{admin_password}".encode("utf-8")
    return hashlib.sha256(material).digest()


def create_admin_token(subject, signing_key):
    payload = base64.urlsafe_b64encode(subject.encode("utf-8")).decode("ascii").rstrip("=")
    signature = hmac.new(signing_key, payload.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def verify_admin_token(token, subject, signing_key):
    try:
        payload, signature = token.rsplit(".", 1)
        expected_signature = hmac.new(signing_key, payload.encode("ascii"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_signature):
            return False
        padding = "=" * (-len(payload) % 4)
        token_subject = base64.urlsafe_b64decode(payload + padding).decode("utf-8")
    except (AttributeError, UnicodeDecodeError, ValueError):
        return False
    return hmac.compare_digest(token_subject, subject)
