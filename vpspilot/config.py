"""
Configuration Manager for VPSPilot
Handles persistent settings, credentials, and directory setup.
"""

import os
import json
import secrets
import hashlib
from pathlib import Path

DEFAULT_PORT = 8888
DEFAULT_HOST = "0.0.0.0"

def get_config_dir() -> Path:
    """Returns the configuration directory path, preferring /etc/vpspilot if writable."""
    etc_path = Path("/etc/vpspilot")
    if os.geteuid() == 0 or (etc_path.exists() and os.access(etc_path, os.W_OK)):
        return etc_path
    home_dir = Path(os.path.expanduser("~/.vpspilot"))
    return home_dir

def get_config_file() -> Path:
    return get_config_dir() / "config.json"

def get_pid_file() -> Path:
    cfg_dir = get_config_dir()
    return cfg_dir / "vpspilot.pid"

def get_log_file() -> Path:
    cfg_dir = get_config_dir()
    return cfg_dir / "vpspilot.log"

def hash_password(password: str, salt: bytes = None) -> tuple[str, str]:
    """Hashes a password using PBKDF2-HMAC-SHA256."""
    if salt is None:
        salt = secrets.token_bytes(16)
    hashed = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt,
        100_000
    )
    return hashed.hex(), salt.hex()

def verify_password(password: str, hashed_hex: str, salt_hex: str) -> bool:
    """Verifies a password against the stored hash and salt."""
    salt = bytes.fromhex(salt_hex)
    test_hash, _ = hash_password(password, salt)
    return secrets.compare_digest(test_hash, hashed_hex)

def ensure_config_dir():
    cfg_dir = get_config_dir()
    if not cfg_dir.exists():
        cfg_dir.mkdir(parents=True, exist_ok=True)
        # Protect config dir permissions
        try:
            os.chmod(cfg_dir, 0o700)
        except OSError:
            pass

def load_config() -> dict:
    """Loads configuration from file or returns default."""
    cfg_file = get_config_file()
    if cfg_file.exists():
        try:
            with open(cfg_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_config(config_data: dict):
    """Saves configuration with restricted file permissions."""
    ensure_config_dir()
    cfg_file = get_config_file()
    with open(cfg_file, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, indent=2)
    try:
        os.chmod(cfg_file, 0o600)
    except OSError:
        pass

def init_config(default_port: int = None, default_host: str = None, explicit_password: str = None) -> tuple[dict, str | None]:
    """
    Initializes configuration if not already set.
    Returns (config_dict, generated_password_or_None)
    """
    ensure_config_dir()
    cfg = load_config()
    generated_pwd = None

    if not cfg:
        cfg = {
            "host": default_host or DEFAULT_HOST,
            "port": default_port or DEFAULT_PORT,
            "admin_username": "admin",
            "secret_key": secrets.token_hex(32),
            "session_timeout": 86400,
            "ssl_enabled": False,
            "ssl_cert": None,
            "ssl_key": None
        }

    if default_host:
        cfg["host"] = default_host
    if default_port:
        cfg["port"] = int(default_port)

    # Check if password is set
    if "password_hash" not in cfg or "password_salt" not in cfg:
        if explicit_password:
            pwd = explicit_password
        else:
            pwd = secrets.token_urlsafe(12)
            generated_pwd = pwd

        p_hash, p_salt = hash_password(pwd)
        cfg["password_hash"] = p_hash
        cfg["password_salt"] = p_salt
        save_config(cfg)
    else:
        save_config(cfg)

    return cfg, generated_pwd

def update_password(new_password: str):
    """Updates admin password."""
    cfg = load_config()
    p_hash, p_salt = hash_password(new_password)
    cfg["password_hash"] = p_hash
    cfg["password_salt"] = p_salt
    save_config(cfg)
