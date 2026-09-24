# app/routers/video.py
import os
import shutil
import uuid
from fastapi import APIRouter, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from app.services.video_service import isolate_mouth_from_video, TEMP_VIDEO_DIR

router = APIRouter()

@router.post("/upload_video", tags=["Video Processing"])
async def process_video_endpoint(background_tasks: BackgroundTasks, video_file: UploadFile = File(...)):
    """
    사용자 영상을 받아 입 모양만 추출한 영상을 반환합니다.
    """
    # 임시 파일로 저장
    temp_input_path = os.path.join(TEMP_VIDEO_DIR, f"{uuid.uuid4()}_{video_file.filename}")
    with open(temp_input_path, "wb") as buffer:
        shutil.copyfileobj(video_file.file, buffer)

    processed_video_path = None # 변수 초기화
    try:
        # === [핵심 수정] ===
        # 반환된 튜플을 각각의 변수(경로, 성공여부)로 나누어 받습니다.
        processed_video_path, success = isolate_mouth_from_video(temp_input_path)
        
        # 이제 success 변수로 성공 여부를 정확히 판단할 수 있습니다.
        if not success:
            raise HTTPException(
                status_code=422,
                detail="영상 파일을 처리할 수 없습니다. 파일이 손상되었거나 지원하지 않는 형식일 수 있습니다."
            )
        
        background_tasks.add_task(os.remove, processed_video_path)
        # FileResponse의 path에는 순수한 파일 경로(문자열)만 전달됩니다.
        return FileResponse(path=processed_video_path, media_type="video/webm", filename="mouth_video.webm")

    finally:
        # try 블록에서 오류가 발생해도 원본 임시 파일은 삭제됩니다.
        if os.path.exists(temp_input_path):
            os.remove(temp_input_path)