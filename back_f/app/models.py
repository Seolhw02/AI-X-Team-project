from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, CheckConstraint, text, Boolean
from sqlalchemy.sql import func, expression
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.mysql import JSON as MYSQL_JSON, BIGINT as MYSQL_BIGINT, CHAR
from sqlalchemy.ext.mutable import MutableList  
from app.database import Base
from app.utils.utils import generate_code

# =========================
# USERS
# =========================
class User(Base):
    __tablename__ = "users"

    user_id  = Column(MYSQL_BIGINT(unsigned=True), primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    email    = Column(String(100), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    
    max_level = Column(
        MutableList.as_mutable(MYSQL_JSON),   # ✅ 변경
        nullable=False,
        default=lambda: [1],
    )


# =========================
# 발음 가이드(참고)
# =========================
class PronunciationData(Base):
    __tablename__ = "pronunciation_data"

    id          = Column(MYSQL_BIGINT(unsigned=True), primary_key=True, index=True, autoincrement=True)
    hangul_char = Column(String(255), unique=True, index=True, nullable=False)
    image_url   = Column(String(255), nullable=True)
    video_url   = Column(String(255), nullable=True)

# ================================
# 학습 세션 (learning_sessions)
# ================================
class StudySession(Base):
    __tablename__ = "study_sessions"

    session_id = Column(CHAR(8), primary_key=True, default=generate_code, comment="세션 고유 ID")
    user_id    = Column(MYSQL_BIGINT(unsigned=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)

    learning_type  = Column(String(20), nullable=True)  # e.g. daily/basic
    total_words    = Column(Integer, nullable=False, default=0)
    status         = Column(String(20), nullable=False, server_default="in_progress")
    created_at     = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    completed_at   = Column(DateTime(timezone=True), nullable=True)
    
    level = Column(
        MutableList.as_mutable(MYSQL_JSON),   # ✅ 변경
        nullable=False,
        default=lambda: [0],
        comment="학습 레벨 리스트(JSON)"
    )

  
    isPassed = Column(Boolean, nullable=False, server_default=expression.false(), comment="통과 여부")
    correctCount = Column(Integer, nullable=True, default=0, comment="정답 개수")

    __table_args__ = (
        CheckConstraint("total_words >= 0", name="ck_session_total_words_non_negative"),
    )

# ================================
# 학습 결과 (learning_results)
# ================================
class StudyResult(Base):
    __tablename__ = "study_results"

    result_id  = Column(MYSQL_BIGINT(unsigned=True), primary_key=True, autoincrement=True, comment="결과 고유 ID")
    session_id = Column(CHAR(8), ForeignKey("study_sessions.session_id", ondelete="CASCADE"),
                        nullable=False, comment="세션 ID")
    score      = Column(Integer, nullable=False, comment="해당 단어 점수")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), comment="학습 시작 시각")
    target_word = Column(String(255), nullable=False, comment="정답 단어")
    recognized_word = Column(String(255), nullable=False, comment="사용자가 발음한 단어")
    video_url = Column(String(255), nullable=True, comment="사용자 발음 비디오 URL")

    __table_args__ = (
        CheckConstraint("score >= 0", name="check_score_non_negative"),
    )
    
    feedbacks = relationship(
        "StudyFeedback",
        back_populates="result",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

# ================================
# 학습 피드백 (learning_feedbacks)
# ================================
class StudyFeedback(Base):
    __tablename__ = "study_feedbacks"

    id         = Column(MYSQL_BIGINT(unsigned=True), primary_key=True, autoincrement=True, comment="피드백 고유 ID")
    result_id  = Column(MYSQL_BIGINT(unsigned=True), ForeignKey("study_results.result_id", ondelete="CASCADE"),
                        nullable=False, comment="result ID")
    score      = Column(Integer, nullable=False, comment="채점 점수")
    mouth_feedback            = Column(Text, nullable=True, comment="입 모양 피드백")
    tongue_position_feedback  = Column(Text, nullable=True, comment="혀 위치 피드백")
    breathing_feedback        = Column(Text, nullable=True, comment="호흡 피드백")
    teaching_point            = Column(Text, nullable=True, comment="학습 포인트")
    correct_img_url          = Column(String(255), nullable=True, comment="정답 이미지 URL")

    __table_args__ = (
        CheckConstraint("score >= 0", name="check_feedback_score_non_negative"),
    )

    result = relationship("StudyResult", back_populates="feedbacks")

# ================================
# 학습 복습 요약 (study_reviews)
# ================================
class StudyReview(Base):
    __tablename__ = "study_reviews"

    review_id = Column(CHAR(8), primary_key=True, default=generate_code)
    user_id   = Column(MYSQL_BIGINT(unsigned=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)

    target_word = Column(String(255), nullable=False)
    recognized_word = Column(String(255), nullable=False, comment="사용자가 발음한 단어")

    # ✅ level 컬럼 추가
    level = Column(
        MutableList.as_mutable(MYSQL_JSON),
        nullable=False,
        default=list,
        comment="학습 레벨 리스트"
    )

    score = Column(Integer, nullable=True, comment="점수")

    feedback_summary = Column(Text, nullable=True, default="피드백 없음")

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_wrong_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("score IS NULL OR score >= 0", name="ck_review_score_non_negative"),
    )

    user = relationship("User", backref="reviews")

# ================================
# 미니게임 리더보드 (mini_game_leaderboard)
# ================================
class MiniGameLeaderboard(Base):
    __tablename__ = "mini_game_leaderboard"

    id = Column(MYSQL_BIGINT(unsigned=True), primary_key=True, autoincrement=True, comment="리더보드 레코드 ID")
    username = Column(String(50), nullable=False, index=True, comment="플레이어 닉네임(스냅샷)")
    points = Column(Integer, nullable=False, default=0, comment="획득 포인트")

    # 기록 시각(UTC 권장, 표시 시 KST 변환)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), comment="기록 시각")

    __table_args__ = (
        CheckConstraint("points >= 0", name="ck_leaderboard_points_non_negative"),
    )