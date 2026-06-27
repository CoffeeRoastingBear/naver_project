import base64
import json
from pathlib import Path


CONFIG_PATH = Path("config.json")
_KEY = "naver-local-dashboard"


def _xor_bytes(data):
    key = _KEY.encode("utf-8")
    return bytes(byte ^ key[index % len(key)] for index, byte in enumerate(data))


def encode_secret(value):
    if not value:
        return ""
    return base64.urlsafe_b64encode(_xor_bytes(value.encode("utf-8"))).decode("ascii")


def decode_secret(value):
    if not value:
        return ""
    try:
        return _xor_bytes(base64.urlsafe_b64decode(value.encode("ascii"))).decode("utf-8")
    except Exception:
        return ""


def load_config():
    if not CONFIG_PATH.exists():
        return {}
    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        data = json.load(file)

    return {
        "client_id": decode_secret(data.get("client_id", "")),
        "client_secret": decode_secret(data.get("client_secret", "")),
        "top_n": int(data.get("top_n", 100)),
        "cooldown_minutes": int(data.get("cooldown_minutes", 30)),
    }


def public_config():
    config = load_config()
    return {
        "has_api_key": bool(config.get("client_id") and config.get("client_secret")),
        "top_n": config.get("top_n", 100),
        "cooldown_minutes": config.get("cooldown_minutes", 30),
    }


def save_config(client_id, client_secret, top_n=100, cooldown_minutes=30):
    payload = {
        "client_id": encode_secret(client_id.strip()),
        "client_secret": encode_secret(client_secret.strip()),
        "top_n": int(top_n),
        "cooldown_minutes": int(cooldown_minutes),
    }
    with CONFIG_PATH.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)

