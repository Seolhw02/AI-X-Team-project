# services/analysis_service.py
# 음성 파일 처리, STT, LLM 평가 등 핵심 비즈니스 로직을 담고 있습니다.

import os
import io
import re
import json
import datetime
from typing import Optional, List

import numpy as np
import soundfile as sf
import torch
import noisereduce as nr
from pydub import AudioSegment
from openai import OpenAI
from dotenv import load_dotenv
from sqlalchemy import func
from sqlalchemy.orm import Session

from faster_whisper import WhisperModel
from fastapi import HTTPException

from app.utils.hangul import decompose_hangul
from app.utils.summarize import summarize_feedback_with_gpt
from app.models import (
    PronunciationData,
    StudyResult,
    StudyFeedback,
    StudySession,
    StudyReview,
)
from app.database import SessionLocal  # ✅ 백그라운드 저장에서 새 세션을 만들기 위해 사용

# .env 파일에서 환경 변수를 로드합니다.
load_dotenv()

# === 모델 로드 및 설정 ===
MODEL_SIZE = "medium"
device = "cuda" if torch.cuda.is_available() else "cpu"
compute_type = "float16" if torch.cuda.is_available() else "default"

print(f"Faster Whisper 모델 로드를 시작합니다. 모델 크기: '{MODEL_SIZE}', 장치: {device}, 계산 타입: {compute_type}")
whisper_model = WhisperModel(MODEL_SIZE, device=device, compute_type=compute_type)
print("Faster Whisper 모델 로드 완료!")


# --- 폴더 분리 및 생성 ---
# 음성 파일 저장 폴더를 정의하고 생성합니다.
PRONUNCIATION_AUDIO_DIR = "pronunciation_audio_files"
MINIGAME_AUDIO_DIR = "minigame_audio_files"
os.makedirs(PRONUNCIATION_AUDIO_DIR, exist_ok=True)
os.makedirs(MINIGAME_AUDIO_DIR, exist_ok=True)



def _reduce_noise(audio_data: np.ndarray, sample_rate: int) -> np.ndarray:
    """오디오 데이터의 노이즈를 제거합니다."""
    print("... 오디오 노이즈 제거를 시작합니다 ...")
    reduced_noise_audio = nr.reduce_noise(y=audio_data, sr=sample_rate, stationary=False, prop_decrease=0.8)
    print("노이즈 제거 완료!")
    return reduced_noise_audio


def _speech_to_text(audio_file_path: str) -> str:
    """지정된 오디오 파일 경로에서 음성 인식(STT)을 수행합니다."""
    print(f"\nSTT 시작 (faster-whisper): '{audio_file_path}'")
    try:
        if not os.path.exists(audio_file_path):
            print(f"오디오 파일이 존재하지 않습니다: {audio_file_path}")
            return ""

        initial_prompt = None
        vad_filter_flag = True
        temperature = 0.0

        segments, _ = whisper_model.transcribe(
            audio_file_path,
            language="ko",
            vad_filter=vad_filter_flag,
            initial_prompt=initial_prompt,
            temperature=temperature,
        )

        transcription = "".join(segment.text.strip() for segment in segments)
        transcription = re.sub(r'[^\w]', '', transcription)
        print(f"STT 결과: {transcription}")
        return transcription
    except Exception as e:
        print(f"faster-whisper 모델 처리 중 오류 발생: {e}")
        return ""


def _create_diff_detail(expected_char: str, actual_char: str) -> str:
    """예상 글자와 실제 발음 글자의 차이를 분석하여 상세 정보를 생성합니다."""
    if not actual_char:
        return "누락된 단어"
    if not expected_char:
        return "추가된 단어"
    e_cho, e_jung, e_jong = decompose_hangul(expected_char)
    a_cho, a_jung, a_jong = decompose_hangul(actual_char)
    diffs = []
    if a_cho != e_cho:
        diffs.append(f"초성: {a_cho} → {e_cho}")
    if a_jung != e_jung:
        diffs.append(f"중성: {a_jung} → {e_jung}")
    if a_jong != e_jong:
        if not a_jong:
            diffs.append(f"종성: {e_jong} 추가")
        elif not e_jong:
            diffs.append(f"종성: {a_jong} 제외")
        else:
            diffs.append(f"종성: {a_jong} → {e_jong}")
    return ", ".join(diffs)


def _evaluate_pronunciation_with_llm(llm_input_pairs: List[dict]) -> dict:
    """LLM을 사용하여 발음 교정 피드백을 생성합니다."""
    if not llm_input_pairs:
        return {"incorrect_points": []}
    try:
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        system_prompt = f"""
        당신은 한국어 발음 교정을 전문으로 하는 언어 치료사입니다.
        아래 '분석 요청 목록'에 있는 각 쌍에 대해, 'expected' 글자를 올바르게 발음하기 위한 '입 모양', '혀 위치', '호흡법' 피드백을 쉽고 구체적으로 생성합니다.
        'diff_detail'은 이미 분석된 정확한 정보이므로, 내용을 수정하지 말고 피드백 생성에 참고만 하세요.
        # 출력 지침
        1. 반드시 아래의 JSON 형식으로만 응답해야 합니다.
        2. 점수(score)는 절대 응답에 포함하지 마세요.
        {{
          "incorrect_points": [
            {{ "expected": "목표 글자", "actual": "사용자가 발음한 글자", "diff_detail": "주어진 교정 포인트 그대로", "mouth_feedback": "생성된 입 모양 피드백", "tongue_position_feedback": "생성된 혀 위치 피드백", "breathing_feedback": "생성된 호흡법 피드백" }}
          ]
        }}
        """
        user_prompt = f"다음은 분석 요청 목록입니다. 이 목록을 바탕으로 위 지시에 따라 JSON을 생성해주세요: {json.dumps(llm_input_pairs, ensure_ascii=False)}"
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        evaluation_result = json.loads(response.choices[0].message.content)
        print("LLM 피드백 생성 완료! 응답 데이터:", evaluation_result)
        return evaluation_result
    except Exception as e:
        print(f"LLM 평가 중 심각한 오류 발생: {e}")
        return {"incorrect_points": []}


def _evaluate_sentence_with_llm(target_text: str, user_transcript: str) -> dict:
    """LLM을 사용하여 문장 발음의 평가/교정/총평 피드백을 생성합니다."""
    try:
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        system_prompt = f"""
        당신은 한국어 발음 교육 전문가입니다. 사용자의 한국어 문장 발음을 듣고 아래의 지시에 따라 평가, 교정, 총평을 제공해주세요.
        사용자가 발음한 문장: "{user_transcript}"
        올바른 문장: "{target_text}"

        # 출력 지침
        1. 반드시 다음 JSON 형식으로만 응답해야 합니다.
        {{
          "sentence_feedback": {{
            "evaluation": "전반적인 발음이 어떤지 간단히 평가. (2~3줄)",
            "correction": "틀린 부분이나 어색한 발음이 있다면, 어떤 글자를 어떻게 교정해야 하는지 구체적인 방법을 알려주세요. (2~3줄)",
            "general_feedback": "전반적인 총평과 다음 연습을 위한 조언을 해주세요. (2~3줄)"
          }}
        }}
        """
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": system_prompt}],
        )
        evaluation_result = json.loads(response.choices[0].message.content)
        print("LLM 문장 피드백 생성 완료! 응답 데이터:", evaluation_result)
        return evaluation_result
    except Exception as e:
        print(f"LLM 문장 평가 중 오류 발생: {e}")
        return {
            "sentence_feedback": {
                "evaluation": "오류 발생",
                "correction": "오류 발생",
                "general_feedback": "오류 발생",
            }
        }


async def analyze_user_sentence(target_sentence: str, audio_file):
    """
    사용자 문장 발음을 분석하고 피드백을 반환합니다. (DB 저장 없음)
    """
    audio_content = await audio_file.read()
    audio_stream = io.BytesIO(audio_content)
    audio = AudioSegment.from_file(audio_stream)
    wav_stream = io.BytesIO()
    audio.set_frame_rate(16000).set_channels(1).export(wav_stream, format="wav")
    wav_stream.seek(0)
    audio_data, sample_rate = sf.read(wav_stream)

    clean_audio_data = _reduce_noise(audio_data, sample_rate) if np.any(audio_data) else audio_data

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    cleaned_audio_path = os.path.join(PRONUNCIATION_AUDIO_DIR, f"sentence_cleaned_{timestamp}.wav")
    sf.write(cleaned_audio_path, clean_audio_data, sample_rate)

    user_transcript = _speech_to_text(cleaned_audio_path) or ""
    normalized_target = target_sentence.strip()

    feedback = _evaluate_sentence_with_llm(normalized_target, user_transcript)

    # 임시 파일 삭제
    if os.path.exists(cleaned_audio_path):
        os.remove(cleaned_audio_path)

    return {
        "my_text": user_transcript,
        "target_word": normalized_target,
        "sentence_feedback": feedback["sentence_feedback"],
    }


async def analyze_user_pronunciation(
    target_sentence: str,
    audio_file,
    db: Session,
    is_review: bool = False,
):
    """
    사용자 '단어' 발음을 분석하고 피드백을 반환합니다. (DB 저장 없음)
    - DB는 조회(PronunciationData)만 수행
    - 저장은 save_pronunciation_result_to_db(...)를 백그라운드에서 호출하세요.
    """
    audio_content = await audio_file.read()
    audio_stream = io.BytesIO(audio_content)
    audio = AudioSegment.from_file(audio_stream)
    wav_stream = io.BytesIO()
    audio.set_frame_rate(16000).set_channels(1).export(wav_stream, format="wav")
    wav_stream.seek(0)
    audio_data, sample_rate = sf.read(wav_stream)

    clean_audio_data = _reduce_noise(audio_data, sample_rate) if np.any(audio_data) else audio_data

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    cleaned_audio_path = os.path.join(PRONUNCIATION_AUDIO_DIR, f"practice_cleaned_{timestamp}.wav")
    sf.write(cleaned_audio_path, clean_audio_data, sample_rate)

    user_transcript = _speech_to_text(cleaned_audio_path) or ""
    normalized_target = target_sentence.strip()
    normalized_user = user_transcript.strip()

    total_score = 0
    max_score = len(normalized_target) * 3
    processed_incorrect_points: List[dict] = []
    is_any_meaningful_similarity_found = False

    for i in range(len(normalized_target)):
        expected_char = normalized_target[i]
        actual_char = normalized_user[i] if i < len(normalized_user) else ""

        if expected_char == actual_char:
            total_score += 3
            is_any_meaningful_similarity_found = True
            continue

        e_cho, e_jung, e_jong = decompose_hangul(expected_char)
        a_cho, a_jung, a_jong = decompose_hangul(actual_char)
        char_score = 0
        if e_cho == a_cho:
            char_score += 1
            is_any_meaningful_similarity_found = True
        if e_jung == a_jung:
            char_score += 1
            is_any_meaningful_similarity_found = True
        if e_jong and e_jong == a_jong:
            char_score += 1
            is_any_meaningful_similarity_found = True

        total_score += char_score
        processed_incorrect_points.append(
            {
                "expected": expected_char,
                "actual": actual_char,
                "diff_detail": _create_diff_detail(expected_char, actual_char),
            }
        )

    if len(normalized_user) > len(normalized_target):
        for i in range(len(normalized_target), len(normalized_user)):
            processed_incorrect_points.append(
                {"expected": "", "actual": normalized_user[i], "diff_detail": "추가된 단어"}
            )

    if not is_any_meaningful_similarity_found and len(normalized_user) >= len(normalized_target):
        final_score = 0
    else:
        final_score = int((total_score / max_score) * 100) if max_score > 0 else 0

    # 0 < score < 100일 때만 LLM 피드백 생성
    if 0 < final_score < 100:
        llm_input_pairs = [
            p for p in processed_incorrect_points if p.get("diff_detail") not in ["누락된 단어", "추가된 단어"]
        ]
        if llm_input_pairs:
            llm_analysis = _evaluate_pronunciation_with_llm(llm_input_pairs)
            llm_feedback_map = {(p["expected"], p["actual"]): p for p in llm_analysis.get("incorrect_points", [])}
            for point in processed_incorrect_points:
                feedback = llm_feedback_map.get((point["expected"], point["actual"]))
                if feedback:
                    point.update(
                        {
                            "mouth_feedback": feedback.get("mouth_feedback", ""),
                            "tongue_position_feedback": feedback.get("tongue_position_feedback", ""),
                            "breathing_feedback": feedback.get("breathing_feedback", ""),
                            "teaching_point": feedback.get("diff_detail", ""),
                        }
                    )

    # 기본값 보정 + 정답 이미지 URL 매핑
    for point in processed_incorrect_points:
        if "mouth_feedback" not in point:
            point.update(
                {
                    "mouth_feedback": "",
                    "tongue_position_feedback": "",
                    "breathing_feedback": "",
                    "teaching_point": point.get("diff_detail", ""),
                }
            )

        expected_char = point.get("expected")
        correct_img_url = "default.png"

        if expected_char and "가" <= expected_char <= "힣":
            char_data = (
                db.query(PronunciationData)
                .filter(PronunciationData.hangul_char == expected_char)
                .first()
            )
            if char_data and char_data.image_url:
                correct_img_url = char_data.image_url

        point["correct_img_url"] = correct_img_url
        point["wrong_text"] = point.get("actual", "")

    # target_word 기준으로 공통 비디오 URL 조회
    word_data = (
        db.query(PronunciationData)
        .filter(PronunciationData.hangul_char == normalized_target)
        .first()
    )
    common_video_url: Optional[str] = word_data.video_url if word_data else None

    # 응답 데이터 구성 (DB 저장 없음)
    response_data = {
        "score": int(final_score),
        "my_text": normalized_user,
        "target_word": normalized_target,
        "correct_video_url": common_video_url,
        "incorrect_points": processed_incorrect_points,
    }

    # 임시 파일 삭제
    if os.path.exists(cleaned_audio_path):
        os.remove(cleaned_audio_path)

    return response_data


# ===========================
# ✅ 백그라운드 DB 저장 함수
# ===========================
async def save_pronunciation_result_to_db(
    session_id: str,
    score: int,
    target_word: str,
    recognized_word: str,
    incorrect_points: List[dict],
    common_video_url: Optional[str] = None,
):
    """
    요청-응답과 분리된 백그라운드 저장 로직.
    - 반드시 새 DB 세션을 열고 닫는다 (SessionLocal)
    - summarize_feedback_with_gpt는 100점이 아닐 때만 1회 호출
    """
    db = SessionLocal()
    try:
        # 결과 저장
        result_row = StudyResult(
            session_id=session_id,
            score=int(score),
            target_word=target_word,
            recognized_word=recognized_word,
            video_url=common_video_url,
        )
        db.add(result_row)
        db.flush()  # result_id 확보

        # 세션 로드
        session_obj = (
            db.query(StudySession)
            .filter(StudySession.session_id == session_id)
            .first()
        )
        if not session_obj:
            db.commit()
            return  # 세션 없으면 결과만 저장하고 종료

        # 100점 → 정답 카운트 증가 + 리뷰 삭제
        if int(score) == 100:
            session_obj.correctCount = (session_obj.correctCount or 0) + 1
            db.add(session_obj)
            db.query(StudyReview).filter(
                StudyReview.user_id == session_obj.user_id,
                StudyReview.target_word == target_word,
            ).delete(synchronize_session=False)

        # 피드백 상세 저장
        if incorrect_points:
            feedback_rows = []
            for p in incorrect_points:
                feedback_rows.append(
                    StudyFeedback(
                        result_id=result_row.result_id,
                        score=int(score),
                        mouth_feedback=p.get("mouth_feedback", "") or "",
                        tongue_position_feedback=p.get("tongue_position_feedback", "") or "",
                        breathing_feedback=p.get("breathing_feedback", "") or "",
                        teaching_point=p.get("teaching_point", "") or "",
                    )
                )
            if feedback_rows:
                db.add_all(feedback_rows)

        # 리뷰 요약: 100점이 아닐 때만 생성/업서트
        if int(score) != 100:
            # level(JSON) → int 하나 뽑기 (비어있으면 0)
            level_value = 0
            if isinstance(session_obj.level, list) and session_obj.level:
                try:
                    level_value = int(session_obj.level[0])
                except Exception:
                    level_value = 0

            feedback_summary_text = await summarize_feedback_with_gpt(incorrect_points)

            existing = (
                db.query(StudyReview)
                .filter(
                    StudyReview.user_id == session_obj.user_id,
                    StudyReview.target_word == target_word,
                )
                .first()
            )

            if existing:
                existing.recognized_word = recognized_word
                existing.level = [level_value]
                existing.score = int(score)
                existing.feedback_summary = feedback_summary_text
                existing.last_wrong_at = func.now()
                db.add(existing)
            else:
                db.add(
                    StudyReview(
                        user_id=session_obj.user_id,
                        target_word=target_word,
                        recognized_word=recognized_word,
                        level=[level_value],
                        score=int(score),
                        feedback_summary=feedback_summary_text,
                        last_wrong_at=func.now(),
                    )
                )

        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[BG DB 저장 오류] {e}")
    finally:
        db.close()


# --- 미니게임 기능 함수 ---
async def transcribe_audio_for_minigame(audio):
    """
    오디오 파일을 받아 텍스트로 변환하는 간단한 STT 기능입니다.
    미니게임 등 실시간 텍스트 변환이 필요할 때 사용합니다. (DB 저장 없음)
    """
    if not audio:
        raise HTTPException(status_code=400, detail="오디오 파일이 없습니다.")

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_filepath = os.path.join(MINIGAME_AUDIO_DIR, f"minigame_audio_{timestamp}.wav")

    try:
        with open(temp_filepath, "wb") as f:
            content = await audio.read()
            f.write(content)
        print(f"미니게임용 오디오 저장 완료: {temp_filepath}")

        segments, _ = whisper_model.transcribe(
            temp_filepath,
            beam_size=5,
            language="ko",
            temperature=0.0,
            vad_filter=True,
        )
        transcription = "".join(segment.text.strip() for segment in segments)
        transcription = re.sub(r"[^\w]", "", transcription)

        print(f"미니게임 STT 결과: {transcription}")
        return {"my_text": transcription}

    except Exception as e:
        print(f"미니게임 STT 처리 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail=f"오디오 처리 중 서버 오류 발생: {str(e)}")

    finally:
        # 성공 여부와 관계없이 임시 파일 삭제
        if os.path.exists(temp_filepath):
            os.remove(temp_filepath)
            print(f"임시 오디오 파일 삭제 완료: {temp_filepath}")
