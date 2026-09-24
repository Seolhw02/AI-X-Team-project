from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db

from app.auth import get_current_user, CurrentUser
from app.models import StudySession
from app.schemas import PracticeSessionCreate, PracticeSessionCreateResponse

router = APIRouter()

@router.post("/practice-sessions", response_model=PracticeSessionCreateResponse, status_code=status.HTTP_201_CREATED)
def create_practice_session(
    payload: PracticeSessionCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    level_int = payload.level[0] if payload.level else 0

    if level_int < 0:
        raise HTTPException(status_code=400, detail="level은 0 이상이어야 합니다.")
    if payload.total_words < 0:
        raise HTTPException(status_code=400, detail="total_words는 0 이상이어야 합니다.")

    try:
        # 1) 이 사용자에 대해 'in_progress' 상태인 세션 전부 삭제
        deleted = (
            db.query(StudySession)
              .filter(
                  StudySession.user_id == current_user.user_id,
                  StudySession.status == "in_progress",
              )
              .delete(synchronize_session=False)
        )
        print(f"[DEBUG] 기존 in_progress 세션 삭제: {deleted}건 (user_id={current_user.user_id})")

        # 2) 새 세션 생성 (과거 동일 레벨 검사 없음)
        session_row = StudySession(
            user_id=current_user.user_id,
            learning_type=payload.mode,
            total_words=payload.total_words,
            status="in_progress",
            level=payload.level or [0],
        )

        print(f"[DEBUG] session_row 생성됨 (commit 전): session_id={session_row.session_id}, user_id={session_row.user_id}")

        db.add(session_row)
        db.commit()
        db.refresh(session_row)

        print(f"[DEBUG] commit 후 DB 반영됨: session_id={session_row.session_id}")

        return PracticeSessionCreateResponse(session_id=session_row.session_id)


    except Exception as e:
        db.rollback()
        print(f"[ERROR] 세션 생성 중 오류: {e}")
        raise HTTPException(status_code=500, detail="세션 생성 중 서버 오류가 발생했습니다.")

