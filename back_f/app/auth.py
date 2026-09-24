from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, OAuth2PasswordBearer
from sqlalchemy.orm import Session, load_only

from app.database import get_db
from app.models import User

from typing import Optional

import os
import jwt

load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_pw, hashed_pw):
    return pwd_context.verify(plain_pw, hashed_pw)

def hash_password(password: str):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# Import FastAPI dependencies
bearer_scheme = HTTPBearer(auto_error=False)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/users/login", auto_error=False)

class CurrentUser:
    def __init__(self, user_id: int, username: Optional[str] = None):
        self.user_id = user_id
        self.username = username

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    print("[AUTH] get_current_user called with token:", token)
    # PyJWT
    try:
        print("[AUTH] SECRET_KEY head:", SECRET_KEY[:8], "ALG:", ALGORITHM)
        print("[AUTH] token head:", (token or ""))

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        print("[AUTH] payload:", {k: payload.get(k) for k in ("sub", "user_id", "id", "exp")})

        user_id = payload.get("user_id")
        username = payload.get("sub")
        if not user_id and not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="토큰에 사용자 정보가 없습니다.",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="토큰이 만료되었습니다.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다.")

    # 필요한 컬럼만 (문자열 사용하면 모델 속성 미정의 이슈 회피)
    q = db.query(User).options(
        load_only(User.user_id, User.username, User.max_level)  # ✅ 속성 객체로 전달
    )
    db_user = (
        q.filter(User.user_id == user_id).first()
        if user_id is not None
        else q.filter(User.username == username).first()
    )
    if not db_user:
        raise HTTPException(status_code=401, detail="사용자를 찾을 수 없습니다.")

    return db_user
