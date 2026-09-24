# routers/leaderboard.py
from fastapi import APIRouter, Depends, status
from sqlalchemy import and_
from sqlalchemy.orm import Session


from app.database import get_db
from app.models import MiniGameLeaderboard, User
from app.schemas import LeaderboardCreate, LeaderboardOut, LeaderboardMyRankOut, LeaderboardSummaryOut
from app.auth import get_current_user

router = APIRouter()

TOP_N = 5

@router.post("/create", response_model=LeaderboardOut, status_code=status.HTTP_201_CREATED)
def create_leaderboard_entry(
    payload: LeaderboardCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = (
        db.query(MiniGameLeaderboard)
          .filter(MiniGameLeaderboard.username == current_user.username)
          .first()
    )
    if row:
        if payload.points > row.points:
            row.points = payload.points
            db.commit()
            db.refresh(row)
        return row
    else:
        row = MiniGameLeaderboard(
            username=current_user.username,
            points=payload.points,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

@router.get("/leaderboard", response_model=LeaderboardSummaryOut)
def leaderboard_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 상위 5개
    top_rows = (
        db.query(MiniGameLeaderboard)
          .order_by(MiniGameLeaderboard.points.desc(), MiniGameLeaderboard.created_at.asc())
          .limit(TOP_N)
          .all()
    )

    # 내 기록 (없을 수도 있음)
    me = (
        db.query(MiniGameLeaderboard)
          .filter(MiniGameLeaderboard.username == current_user.username)
          .first()
    )

    my_rank_payload = None
    if me:
        total = db.query(MiniGameLeaderboard).count()
        higher_or_earlier = (
            db.query(MiniGameLeaderboard)
              .filter(
                  (MiniGameLeaderboard.points > me.points) |
                  and_(
                      MiniGameLeaderboard.points == me.points,
                      MiniGameLeaderboard.created_at < me.created_at
                  )
              )
              .count()
        )
        my_rank_payload = LeaderboardMyRankOut(
            username=me.username,
            points=me.points,
            rank=higher_or_earlier + 1,
            total_players=total,
            created_at=me.created_at,
        )

    return {
        "leaderboard": top_rows,
        "my_rank": my_rank_payload,  # 기록 없으면 null
    }