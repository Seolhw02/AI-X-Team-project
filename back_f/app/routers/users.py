from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.schemas import UserCreate, UserLogin, UserDelete
from app.utils.utils import is_valid_email, is_blank
from app.auth import hash_password, verify_password, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from datetime import timedelta

router = APIRouter()


@router.post("/signup")
def register(user: UserCreate, db: Session = Depends(get_db)):
    if is_blank(user.username) or is_blank(user.email) or is_blank(user.password):
        raise HTTPException(status_code=400, detail="모든 항목을 입력해주세요.")
    if len(user.username) < 3:
        raise HTTPException(status_code=400, detail="아이디는 3글자 이상으로 입력하세요")
    elif len(user.username) > 8:
        raise HTTPException(status_code=400, detail="아이디는 8글자 이하로 입력하세요")
    if not is_valid_email(user.email):
        raise HTTPException(status_code=400, detail="유효한 이메일 형식이 아닙니다.")
    if len(user.password) < 6:
        raise HTTPException(status_code=400, detail="비밀번호는 최소 6글자 이상으로 입력하세요.")
    elif len(user.password) > 12:
        raise HTTPException(status_code=400, detail="비밀번호는 최대 12글자 이하로 입력하세요.")
    has_special = any(char in "!@#$%^&*()-_=+[{]}\\|;:'\",<.>/?`~" for char in user.password)
    has_upper = any(char.isupper() for char in user.password)
    if not (has_special and has_upper):
        raise HTTPException(status_code=400,detail="비밀번호에 최소 하나 이상의 특수문자와 대문자가 포함되어야 합니다.")
    db_user = db.query(User).filter((User.username == user.username) | (User.email == user.email)).first()
    if db_user:
        raise HTTPException(status_code=400, detail="이미 존재하는 아이디 또는 이메일입니다.")
    new_user = User(username=user.username, email=user.email, password=hash_password(user.password))
    db.add(new_user)
    db.commit()
    return {"message": "회원가입이 완료되었습니다."}

@router.post("/login")
def login(user: UserLogin, db: Session = Depends(get_db)):
    if is_blank(user.username) or is_blank(user.password):
        raise HTTPException(status_code=400, detail="아이디와 비밀번호를 모두 입력해주세요.")
    db_user = db.query(User).filter(User.username == user.username).first()
    if not db_user or not verify_password(user.password, db_user.password):
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다.")
    access_token = create_access_token(

        data={"sub": db_user.username, "user_id": db_user.user_id},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.delete("/withdraw")
def delete_user(user: UserDelete, db: Session = Depends(get_db)):
    if is_blank(user.email) or is_blank(user.password):
        raise HTTPException(status_code=400, detail="이메일과 비밀번호를 모두 입력해주세요.")
    if not is_valid_email(user.email):
        raise HTTPException(status_code=400, detail="유효한 이메일 형식이 아닙니다.")
    if len(user.password) > 12:
        raise HTTPException(status_code=400, detail="비밀번호는 최소 12자 이하이어야 합니다.")
    db_user = db.query(User).filter(User.email == user.email).first()
    if not db_user or not verify_password(user.password, db_user.password):
        raise HTTPException(status_code=401, detail="비밀번호가 올바르지 않습니다.")
    db.delete(db_user)
    db.commit()

    return {"message": "회원 탈퇴가 완료되었습니다."}
