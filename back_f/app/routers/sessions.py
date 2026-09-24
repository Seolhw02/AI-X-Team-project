from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
import json

from app.database import get_db
from app.models import StudySession, User
from app.auth import get_current_user
from app.schemas import StudySessionOut

router = APIRouter()

@router.patch("/{session_id}/complete", response_model=StudySessionOut, status_code=status.HTTP_200_OK)
def complete_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 내 세션 조회
    session = (
        db.query(StudySession)
        .filter(
            StudySession.session_id == session_id,
            StudySession.user_id == current_user.user_id,
        )
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없거나 권한이 없습니다.")

    # ✅ 완료 처리
    if session.status != "completed":
        session.status = "completed"
        session.completed_at = func.now()

    # =====================================
    # ✅ 통과 여부 계산 (correct_count vs total_words)
    # =====================================
    total_words = int(session.total_words or 0)
    correctCount = int(session.correctCount or 0)

    # 과반 초과 기준(기존 유지)
    is_passed_bool = correctCount > (total_words / 2)

    # (선택) 세션 테이블에 isPassed 같은 컬럼이 있으면 저장
    if hasattr(session, "isPassed"):
        session.isPassed = is_passed_bool

    # ===== 여기부터 신규 정책 =====
    # 같은 유저 & 같은 레벨 기준을 만들기 (level은 JSON 배열이므로 OR 로 매칭)
    levels = session.level or []
    same_level_preds = [func.json_contains(StudySession.level, json.dumps([lv])) == 1 for lv in levels] if levels else []

    # 1) 같은 레벨의 기존 실패 세션은 삭제 (현재 세션 제외)
    #    - 상태는 완료(completed)만 대상으로 함 (원하면 제한 제거 가능)
    isPassed_col = getattr(StudySession, "isPassed", None)
    delete_filters = [
        StudySession.user_id == current_user.user_id,
        StudySession.session_id != session.session_id,
        StudySession.status == "completed",
    ]
    if same_level_preds:
        delete_filters.append(or_(*same_level_preds))
    if isPassed_col is not None:
        delete_filters.append(isPassed_col == False)

    if isPassed_col is not None:
        deleted_failed = (
            db.query(StudySession)
              .filter(*delete_filters)
              .delete(synchronize_session=False)
        )
        if deleted_failed:
            print(f"[DEBUG] 기존 실패 세션 삭제: {deleted_failed}건 (levels={levels})")

    # 2) 같은 레벨의 기존 통과 세션이 하나라도 있으면 현재 세션을 review로 전환
    passed_filters = [
        StudySession.user_id == current_user.user_id,
        StudySession.session_id != session.session_id,
        StudySession.status == "completed",
    ]
    if same_level_preds:
        passed_filters.append(or_(*same_level_preds))
    if isPassed_col is not None:
        passed_filters.append(isPassed_col == True)

    has_prev_passed = False
    if isPassed_col is not None:
        has_prev_passed = (
            db.query(StudySession.session_id)
              .filter(*passed_filters)
              .limit(1)
              .first()
            is not None
        )

    if has_prev_passed:
        session.learning_type = "review"

    # ===== 기존 로직 유지: 통과 시 유저 레벨 승급 등 =====
    if is_passed_bool:
        user = db.query(User).filter(User.user_id == current_user.user_id).first()
        if user:
            curr = user.max_level or []
            # [0]이면 유지
            if curr == [0]:
                pass
            else:
                if 2 not in curr and 1 in curr:
                    new_levels = sorted(set(curr + [2]))
                    user.max_level = new_levels
                    db.add(user)

    db.add(session)
    db.commit()
    db.refresh(session)

    return StudySessionOut(
        session_id=session.session_id,
        user_id=session.user_id,
        status=session.status,
        created_at=session.created_at,
        completed_at=session.completed_at,
        total_words=session.total_words,
        level=session.level,
        isPassed=is_passed_bool,
        correctCount=correctCount,
    )
