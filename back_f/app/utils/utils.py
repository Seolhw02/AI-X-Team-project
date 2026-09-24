import re
import secrets, string

ALPHABET62 = string.ascii_letters + string.digits

def is_valid_email(email: str) -> bool:
    return re.match(r"[^@]+@[^@]+\.[^@]+", email) is not None

def is_blank(field: str) -> bool:
    return not field or field.strip() == ""

def generate_code(length: int = 8) -> str:
    code = ''.join(secrets.choice(ALPHABET62) for _ in range(length))
    print(f"[DEBUG] generate_code(): 생성된 세션 ID = {code}")  # ✅ 디버깅 출력
    return code