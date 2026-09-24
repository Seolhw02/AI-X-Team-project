# main.py
# FastAPI 앱을 실행하는 진입점입니다.

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

# 데이터베이스 설정 및 모델 임포트
from app.database import Base, engine

# 라우터 임포트
from app.routers import users, results, pronunciation, progress, sessions, reviews, video, leaderboard

# .env 파일에서 환경 변수를 로드합니다.
load_dotenv()

# 데이터베이스 테이블 생성
Base.metadata.create_all(bind=engine)

# FastAPI 앱 생성 및 설정
app = FastAPI(title="유음 database")

origins = [
    "http://localhost:5173",  # Vite dev server
    "http://localhost:5174",  # 현재 프론트엔드 주소 추가
  
    "https://youum.kro.kr",
    
    "https://final-front-dusky.vercel.app",
    "https://final-front-mekr3igui-seolhyunwoos-projects.vercel.app",
    
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
)

# API 라우터들을 메인 앱에 포함시킵니다.
app.include_router(pronunciation.router, prefix="/api/pronunciation", tags=["pronunciation"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(results.router, prefix="/api/results", tags=["Results"])
app.include_router(progress.router, prefix="/api/progress", tags=["Progress"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["Study Sessions"])
app.include_router(reviews.router, prefix="/api/reviews", tags=["Reviews"])
app.include_router(video.router, prefix="/api/video", tags=["Video Processing"])
app.include_router(leaderboard.router, prefix="/api/leaderboard", tags=["Leaderboard"])

# 정적 파일(이미지)을 서빙할 경로를 마운트합니다.
app.mount("/static/images", StaticFiles(directory="static/images"), name="static_images")

# 루트 엔드포인트
@app.get("/")
async def root():
    return {"message": "의사소통 보조 AI 유음"}