from fastapi import APIRouter, Depends

from app.models import User
from app.schemas import ProgressOut
from app.auth import SECRET_KEY, ALGORITHM, get_current_user

import json

router = APIRouter()

@router.get("/me", response_model=ProgressOut)
def read_my_progress(current_user: User = Depends(get_current_user)):
    raw = getattr(current_user, "max_level", None)

    # ✅ 항상 리스트로 정규화: None, 0, "", 잘못 저장된 스칼라 등 → []
    if isinstance(raw, list):
        levels = raw
    
    elif isinstance(raw, int):
        try:
            parsed = json.loads(raw)
            levels = parsed if isinstance(parsed, list) else [1]
        
        except Exception:
            levels = [1]
        
    else:
        levels = [1]   # 스칼라/None/빈 값은 전부 빈 배열로

    return ProgressOut(
        username = current_user.username,
        email = current_user.email,
        max_level=levels
    )