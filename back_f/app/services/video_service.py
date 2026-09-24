# app/services/video_service.py

import os
import cv2
import mediapipe as mp 
import uuid
import numpy as np
import ffmpeg

# === [수정 1] 모델과 관련된 변수를 함수 바깥, 전역 공간에서 미리 초기화 ===
mp_face_mesh = mp.solutions.face_mesh
LIP_LANDMARKS = [
    61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291,
    78, 95, 88, 178, 87, 14, 317, 402, 318, 324, 308
]
TEMP_VIDEO_DIR = "temp_videos"
os.makedirs(TEMP_VIDEO_DIR, exist_ok=True)


def isolate_mouth_from_video(video_path: str):
    compatible_video_path = f"{video_path}.mp4"
    try:
        ffmpeg.input(video_path).output(compatible_video_path, vcodec='libx264').run(overwrite_output=True, capture_stdout=True, capture_stderr=True)
    except ffmpeg.Error as e:
        print("FFmpeg Error:", e.stderr.decode())
        return None, False
    
    cap = cv2.VideoCapture(compatible_video_path)
    if not cap.isOpened():
        os.remove(compatible_video_path)
        return None, False

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)

    if fps == 0:
        cap.release()
        os.remove(compatible_video_path)
        return None, False

    output_filename = f"mouth_{uuid.uuid4()}.webm"
    output_path = os.path.join(TEMP_VIDEO_DIR, output_filename)
    fourcc = cv2.VideoWriter_fourcc(*'VP90')
    out = cv2.VideoWriter(output_path, fourcc, fps, (200, 100))
    
    # === [수정 2] AI 모델 인스턴스를 루프 시작 전에 "한 번만" 생성 ===
    face_mesh = mp_face_mesh.FaceMesh(static_image_mode=False, max_num_faces=1)
    
    is_processing_successful = False

    try:
        while cap.isOpened():
            success, frame = cap.read()
            if not success:
                break
            
            is_processing_successful = True
            
            frame.flags.writeable = False
            image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            # === [수정 3] 미리 생성된 모델을 사용해 프레임 처리만 수행 ===
            results = face_mesh.process(image_rgb)
            frame.flags.writeable = True

            if results.multi_face_landmarks:
                for face_landmarks in results.multi_face_landmarks:
                    lip_points = [(int(face_landmarks.landmark[i].x * width), int(face_landmarks.landmark[i].y * height)) for i in LIP_LANDMARKS]
                    
                    x_coords = [p[0] for p in lip_points]
                    y_coords = [p[1] for p in lip_points]
                    x_min, x_max = min(x_coords), max(x_coords)
                    y_min, y_max = min(y_coords), max(y_coords)
                    
                    padding = 20
                    x_min = max(0, x_min - padding)
                    y_min = max(0, y_min - padding)
                    x_max = min(width, x_max + padding)
                    y_max = min(height, y_max + padding)
                    
                    mouth_frame = frame[y_min:y_max, x_min:x_max]

                    if mouth_frame.size > 0:
                        resized_mouth = cv2.resize(mouth_frame, (200, 100))
                        out.write(resized_mouth)
                    else:
                        out.write(np.zeros((100, 200, 3), dtype=np.uint8))
            else:
                 out.write(np.zeros((100, 200, 3), dtype=np.uint8))
    finally:
        # === [수정 4] face_mesh 리소스도 닫아줌 ===
        face_mesh.close()
        cap.release()
        out.release()
        os.remove(compatible_video_path)

    if not is_processing_successful:
        if os.path.exists(output_path):
            os.remove(output_path)
        return None, False
        
    return output_path, True