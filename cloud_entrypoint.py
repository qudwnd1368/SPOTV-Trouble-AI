"""Create Streamlit OIDC config from Cloud Run secrets, then start the app."""

import json
import os
from pathlib import Path


def write_auth_config():
    if os.getenv("ENABLE_GOOGLE_LOGIN", "false").lower() != "true":
        return
    required = ["APP_URL", "COOKIE_SECRET", "OAUTH_CLIENT_ID", "OAUTH_CLIENT_SECRET"]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError("Missing Google login settings: " + ", ".join(missing))
    app_url = os.environ["APP_URL"].rstrip("/")
    content = "\n".join([
        "[auth]",
        f"redirect_uri = {json.dumps(app_url + '/oauth2callback')}",
        f"cookie_secret = {json.dumps(os.environ['COOKIE_SECRET'])}",
        f"client_id = {json.dumps(os.environ['OAUTH_CLIENT_ID'])}",
        f"client_secret = {json.dumps(os.environ['OAUTH_CLIENT_SECRET'])}",
        'server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"',
        "",
    ])
    target = Path(__file__).with_name(".streamlit") / "secrets.toml"
    target.parent.mkdir(exist_ok=True)
    target.write_text(content, encoding="utf-8")


def main():
    write_auth_config()
    port = os.getenv("PORT", "8080")
    args = [
        "streamlit", "run", "app.py",
        "--server.address=0.0.0.0",
        f"--server.port={port}",
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
    ]
    os.execvp(args[0], args)


if __name__ == "__main__":
    main()

