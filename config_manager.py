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


def _read_raw():
    if not CONFIG_PATH.exists():
        return {}
    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_config():
    data = _read_raw()
    return {
        "client_id": decode_secret(data.get("client_id", "")),
        "client_secret": decode_secret(data.get("client_secret", "")),
        "top_n": int(data.get("top_n", 100)),
        "cooldown_minutes": int(data.get("cooldown_minutes", 30)),
        "category_cooldowns": data.get("category_cooldowns", {}) or {},
    }


def public_config():
    config = load_config()
    return {
        "has_api_key": bool(config.get("client_id") and config.get("client_secret")),
        "top_n": config.get("top_n", 100),
        "cooldown_minutes": config.get("cooldown_minutes", 30),
        "category_cooldowns": config.get("category_cooldowns", {}),
    }


def save_config(client_id, client_secret, top_n=100, cooldown_minutes=30, category_cooldowns=None):
    existing = load_config()
    client_id = client_id.strip() or existing.get("client_id", "")
    client_secret = client_secret.strip() or existing.get("client_secret", "")
    cooldown_minutes = max(5, min(60, int(cooldown_minutes)))

    payload = {
        "client_id": encode_secret(client_id),
        "client_secret": encode_secret(client_secret),
        "top_n": int(top_n),
        "cooldown_minutes": cooldown_minutes,
        "category_cooldowns": category_cooldowns if category_cooldowns is not None else existing.get("category_cooldowns", {}),
    }
    with CONFIG_PATH.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def set_category_cooldown(category, minutes):
    config = load_config()
    category_cooldowns = config.get("category_cooldowns", {})
    category_cooldowns[category] = max(5, min(60, int(minutes)))
    save_config(
        config.get("client_id", ""),
        config.get("client_secret", ""),
        config.get("top_n", 100),
        config.get("cooldown_minutes", 30),
        category_cooldowns,
    )


def cooldown_for_category(category):
    config = load_config()
    value = config.get("category_cooldowns", {}).get(category)
    return max(5, min(60, int(value or config.get("cooldown_minutes", 30))))
