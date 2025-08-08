import hashlib
from app.config import UbuntuConfig
import hmac
from pathlib import Path


def validate_api_key(key: str) -> bool:
    """验证API密钥"""
    stored_key = get_stored_key()
    return secure_compare(key, stored_key)

def secure_compare(a: str, b: str) -> bool:
    """安全字符串比较"""
    return hashlib.sha256(a.encode()).digest() == hashlib.sha256(b.encode()).digest()

def get_stored_key() -> str:
    config = UbuntuConfig()  # 现在可以正确访问
    key_path = Path(config.API_KEY_PATH)
    if not key_path.exists():
        raise RuntimeError("API密钥未配置")
    return key_path.read_text().strip()
