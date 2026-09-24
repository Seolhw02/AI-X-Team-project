# api/pronunciation.py (수정 후)
# API 엔드포인트를 정의하고, 서비스 로직 함수들을 호출합니다.

from fastapi import APIRouter, Form, File, UploadFile, HTTPException, Depends, BackgroundTasks, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db 
from app.schemas import PronunciationAnalysisResponse
from app.services.analysis_service import analyze_user_pronunciation, transcribe_audio_for_minigame, analyze_user_sentence, save_pronunciation_result_to_db


# API 라우터 객체를 생성합니다.
router = APIRouter()

@router.post("/analyze", response_model=PronunciationAnalysisResponse)
async def analyze_pronunciation_endpoint(
    target_sentence: str = Form(...),
    audio_file: UploadFile = File(...),
    session_id: str | None = Form(None),    # 있으면 저장을 백그라운드로
    isReview: bool = Form(False),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
):
    try:
        # 1) 분석만 수행(즉시 응답용). 서비스는 DB에 쓰지 않습니다.
        result = await analyze_user_pronunciation(
            target_sentence=target_sentence,
            audio_file=audio_file,
            db=db,
            is_review=isReview,
        )

        # 2) 세션이 있으면 DB 저장을 백그라운드로 등록
        if session_id and background_tasks is not None:
            background_tasks.add_task(
                save_pronunciation_result_to_db,
                session_id,
                result["score"],
                result["target_word"],
                result["my_text"],
                result["incorrect_points"],
                result.get("correct_video_url"),
            )

        # 3) 즉시 결과 반환 (DB 저장 완료 대기 X)
        return result

    except Exception as e:
        print(f"발음 분석 중 심각한 오류 발생: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"서버에서 오디오 파일을 처리하는 중 오류가 발생했습니다: {str(e)}",
        )

# --- 새롭게 추가된 부분: 문장 분석 엔드포인트 ---
@router.post("/analyze_sentence")
async def analyze_sentence_endpoint(
    target_sentence: str = Form(...),
    audio_file: UploadFile = File(...)
):
    try:
        response_data = await analyze_user_sentence(target_sentence, audio_file)
        return JSONResponse(content=response_data)
    except Exception as e:
        print(f"문장 분석 중 심각한 오류 발생: {e}")
        raise HTTPException(status_code=500, detail=f"서버에서 오디오 파일을 처리하는 중 오류가 발생했습니다: {str(e)}")    

@router.post("/transcribe_audio")
async def transcribe_audio_for_minigame_endpoint(audio: UploadFile = File(...)):
    """
    오디오 파일을 받아 텍스트로 변환하는 간단한 STT 기능입니다.
    미니게임 등 실시간 텍스트 변환이 필요할 때 사용합니다.
    """
    try:
        return await transcribe_audio_for_minigame(audio)
    except Exception as e:
        print(f"미니게임 STT 처리 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail=f"오디오 처리 중 서버 오류 발생: {str(e)}")
