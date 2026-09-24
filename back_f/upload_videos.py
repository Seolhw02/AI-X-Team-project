# upload_videos.py (Final Version)

import os
import csv
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv

# 데이터베이스, 모델 및 유틸리티 함수를 가져옵니다.
from app.database import SessionLocal
from app.models import PronunciationData
from app.utils.hangul import decompose_hangul # 한글 분해 함수
from app.core.config import IMAGE_GUIDE_MAP   # 자모음-이미지 매핑

# 테이블 이름 pronunciation_videos

#스키마 파일에 두개 아래 추가함
# correct_img_url: Optional[str] = None 
# correct_video_url: Optional[str] = None 

# .env 파일에서 환경 변수를 로드합니다.
load_dotenv()

# --- Cloudinary 설정 ---
cloudinary.config(
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key = os.getenv("CLOUDINARY_API_KEY"),
    api_secret = os.getenv("CLOUDINARY_API_SECRET")
)

# FastAPI 서버의 기본 주소를 .env 파일에서 가져옵니다.
# .env 파일에 추가해주세요. 예: BASE_URL="http://127.0.0.1:8000"
BASE_URL = os.getenv("MYSQL_URL", "http://127.0.0.1:8000")

# 데이터베이스 세션을 생성합니다.
db = SessionLocal()

def upload_and_save_all_data():
    """
    mapping.csv 파일을 읽어 영상을 Cloudinary에 업로드하고,
    영상 URL과 이미지 URL을 함께 데이터베이스에 저장합니다.
    """
    video_folder = "videos_to_upload"
    mapping_file = "mapping.csv"

    if not os.path.exists(mapping_file):
        print(f"오류: {mapping_file} 파일을 찾을 수 없습니다. 스크립트를 종료합니다.")
        return

    with open(mapping_file, mode='r', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        for row in reader:
            hangul_char = row.get('hangul_char')
            video_filename = row.get('video_filename')

            if not hangul_char or not video_filename:
                print(f"경고: CSV 파일의 행에 데이터가 부족합니다. {row}")
                continue

            filepath = os.path.join(video_folder, video_filename)

            if not os.path.exists(filepath):
                print(f"경고: {filepath} 파일을 찾을 수 없습니다. 건너뜁니다.")
                continue

            print(f"'{hangul_char}'에 대한 처리 시작...")

            try:
                # 1. 영상 업로드 및 URL 생성
                print(f" -> 영상 업로드 중: {filepath}")
                upload_result = cloudinary.uploader.upload(
                    filepath,
                    resource_type="video",
                    public_id=f"pronunciation_videos/{os.path.splitext(video_filename)[0]}"
                )
                video_url = upload_result.get("secure_url")
                if not video_url:
                    print(f" -> 업로드 실패: 영상 URL을 받아오지 못했습니다.")
                    continue
                print(f" -> 영상 업로드 성공! URL: {video_url}")

                # 2. 이미지 URL 생성
                # 음절을 초성, 중성, 종성으로 분해
                chosung, jungsung, _ = decompose_hangul(hangul_char)
                # 초성을 기준으로 이미지 파일명을 찾음 (없으면 중성 기준, 그것도 없으면 기본값)
                image_filename = IMAGE_GUIDE_MAP.get(chosung, IMAGE_GUIDE_MAP.get(jungsung, "default.png"))
                # FastAPI 서버의 정적 파일 경로로 전체 URL 구성
                image_url = f"{BASE_URL}/static/images/{image_filename}"
                print(f" -> 이미지 URL 생성 완료: {image_url}")

                # 3. 데이터베이스에 저장
                db_char_data = db.query(PronunciationData).filter(PronunciationData.hangul_char == hangul_char).first()
                
                if not db_char_data:
                    db_char_data = PronunciationData(hangul_char=hangul_char)
                    db.add(db_char_data)
                
                # 영상 URL과 이미지 URL을 모두 업데이트
                db_char_data.video_url = video_url
                db_char_data.image_url = image_url
                
                db.commit()
                print(f" -> DB에 영상 및 이미지 URL 저장 완료.")

            except Exception as e:
                print(f"'{hangul_char}' 처리 중 심각한 오류 발생: {e}")
                db.rollback()

# 이 스크립트가 직접 실행될 때만 아래 코드가 동작합니다.
if __name__ == "__main__":
    upload_and_save_all_data()
    db.close()
    print("\n모든 작업이 완료되었습니다.")
