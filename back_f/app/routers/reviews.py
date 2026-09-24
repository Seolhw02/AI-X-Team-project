# app/routers/reviews.py

from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import StudyReview, User
from app.auth import get_current_user
from app.schemas import StudyReviewOut

router = APIRouter()

@router.get("/", response_model=List[StudyReviewOut], status_code=status.HTTP_200_OK)
def list_my_reviews(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    print(f"Current user ID: {current_user.user_id}")
    """내(review.owner == token.user) 리뷰 전체 목록 반환"""
    items = (
        db.query(StudyReview)
        .filter(StudyReview.user_id == current_user.user_id)
        .order_by(StudyReview.last_wrong_at.desc(), StudyReview.created_at.desc())
        .all()
    )
    return items
