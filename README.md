# 유음 (Yueum) — AI 기반 발음 재활 솔루션 (Backend)

청각장애인이 시간·비용 부담 없이 스스로 발음을 교정할 수 있도록,
음성을 분석해 **어떤 자음·모음이 어떻게 틀렸는지 진단하고 개인화된 코칭 피드백을 제공**하는 서비스의 백엔드입니다.

애드인에듀 아카데미 (KDT) 심화 생성형 AI 인공지능 개발자 부트캠프 **최우수상 수상작** (2025.06 ~ 2025.08)

<br>

## 역할 분담

6인 팀 프로젝트이며, 본인은 **백엔드 서버 전체와 AI 파이프라인**을 담당했습니다.

| 영역 | 담당 |
|---|---|
| **백엔드 서버 전체** (FastAPI 구조 설계, API 구현, 배포·운영) | 본인 |
| **AI 파이프라인** (STT 엔진 선정, 발음 분석 알고리즘, LLM 피드백, 입 모양 추출) | 본인 |
| DB 설계, 회원가입·로그인 | 팀원 |
| 프론트엔드 | 팀원 |

> 협업 과정에서 코드를 압축 파일로 주고받아 원본 저장소의 커밋 기록이 실제 작성자와 일치하지 않아,
> 본 저장소는 정리된 상태로 새로 구성했습니다.

<br>

## 기술 스택

- **Backend** — FastAPI, SQLAlchemy, MySQL, JWT
- **AI** — faster-whisper(CTranslate2), OpenAI GPT-4o-mini, MediaPipe, OpenCV, noisereduce, pydub
- **Infra** — AWS Lightsail(Ubuntu), Nginx, Gunicorn, Tmux, Cloudinary

<br>

## 핵심 기능

**1. 발음 분석 파이프라인**
음성 업로드 → 노이즈 제거 → STT 변환 → 자모 단위 비교 → LLM 피드백 생성 → 결과 반환

**2. 자모 단위 부분 점수 채점**
한글 음절을 초성·중성·종성으로 분해해 각 1점씩, **글자당 최대 3점**으로 채점합니다.
"감"을 "강"으로 발음한 경우 `ㄱ`·`ㅏ`는 정답, 종성 `ㅁ → ㅇ`만 오답으로 판정해
**무엇이 어떻게 틀렸는지**를 구체적으로 짚어냅니다.

**3. LLM 코칭 피드백**
자모 분석 결과를 GPT-4o-mini에 전달해 **입 모양 · 혀 위치 · 호흡법** 세 가지 관점의 교정 피드백을 생성합니다.

**4. 입 모양 추출**
MediaPipe FaceMesh로 입술 랜드마크 22개를 추적해 발화 영상에서 입 모양만 잘라내고,
가이드 영상과 나란히 비교할 수 있도록 제공합니다.

**5. 학습 세션 관리**
단어 학습, 문장 학습, 복습, 미니게임, 학습 진도, 포인트 랭킹

<br>

## 기술 선택

정확도와 추론 속도의 균형, 그리고 유지보수 용이성을 기준으로 모델과 엔진을 직접 비교해 선정했습니다.

<details>
<summary><b>STT 모델·엔진 비교 (6종)</b></summary>

<br>

| 모델 | 음성인식 속도 | 비고 |
|---|---|---|
| **faster-whisper + whisper-medium** | **0.6~0.8초** | **최종 채택.** 모델 크기를 절반으로 줄이고 CTranslate2 추론 엔진 적용. 속도가 가장 빠르면서 정확도도 준수 |
| OpenAI Whisper API | 1.8~3초 | API 호출 오버헤드로 속도 저하. 정확도는 medium과 큰 차이 없음 |
| whisper-medium + TensorRT | 4.5~6.5초 | 최초 실행 시 1~2분의 준비 시간 필요, 설정 과정이 복잡 |
| faster-whisper + whisper-small | 0.2~0.4초 | 가장 빠르나 STT 정확도가 낮음 |
| faster-whisper + whisper-large-v3 | 2~3초 | 정확도는 medium과 유사하나 모델 크기가 2배 |
| faster-whisper + whisper-large-v3-turbo-korean | 1~2초 | 한국어 파인튜닝 모델. 경량화·속도는 개선되나 **관련 없는 문장을 빈번하게 생성(환각)** |

</details>

<details>
<summary><b>LLM 피드백 생성 속도 비교 (8종)</b></summary>

<br>

발음이 유사한 **단어 50개를 직접 녹음해 평가 데이터를 구성**하고, 동일 조건에서 피드백 품질과 속도를 비교했습니다.
경쟁 모델에서 **오류·누락률(Qwen2 20%, Gemma3 15%)** 을 확인했으며, 가장 안정적인 GPT-4o-mini를 채택했습니다.

| 모델 | 피드백 생성 속도 | 비고 |
|---|---|---|
| **gpt-4o-mini** | **4~9초** | **최종 채택.** 가장 빠르고 안정적. 틀린 글자 수에 따라 변동 |
| Ollama (llama3.2 3B) | 4~9초 | 결과는 준수하나 오타 발생 |
| Ollama (qwen3:4b) | 5~7초 | 결과 준수, 오타 일부 |
| Gemma-3-ko-4b | 5~7초 | 결과 준수, 속도 빠른 편 |
| Ollama (Llama-3-8B-Instruct-Q4_K_M) | 12~14초 | 정답지를 변형해 출력, 속도 느림 |
| Ollama (Qwen2:7b) | 14~20초 | 예시대로 출력되나 속도 느림 |
| Ollama (llama3 8B) | 15~19초 | 정답지를 변형해 출력, 속도 느림 |
| Ollama (mistral:7b) | 19~29초 | 결과는 나쁘지 않으나 속도 느림 |

</details>

<br>

## 디렉터리 구조

```
app/
├── routers/                 # API 엔드포인트
│   ├── pronunciation.py     #   발음 분석 (단어/문장/미니게임)
│   ├── sessions.py          #   학습 세션
│   ├── results.py           #   학습 결과
│   ├── reviews.py           #   복습
│   ├── progress.py          #   학습 진도
│   ├── leaderboard.py       #   포인트 랭킹
│   ├── video.py             #   영상 업로드·입 모양 추출
│   └── users.py             #   회원가입·로그인
├── services/
│   ├── analysis_service.py  # STT, 자모 분석, LLM 피드백 생성
│   └── video_service.py     # MediaPipe 입 모양 추출
├── utils/
│   ├── hangul.py            # 한글 자모 분해
│   └── summarize.py         # 피드백 요약
├── models.py                # DB 테이블 정의
├── schemas.py               # 요청·응답 스키마
├── auth.py                  # JWT 인증
└── database.py              # DB 연결
```

<br>

## 실행 방법

```bash
# 1. 패키지 설치
pip install -r requirements.txt

# 2. 환경 변수 설정
cp .env.example .env         # 파일을 열어 각 값을 채워 넣습니다

# 3. 서버 실행
uvicorn main:app --reload
```

실행 후 `http://localhost:8000/docs` 에서 API 문서를 확인할 수 있습니다.

<br>

## 서버 운영

AWS Lightsail(Ubuntu) 인스턴스에 배포하고, Nginx 리버스 프록시와 HTTPS를 적용했습니다.
Gunicorn 워커 3개로 요청을 나눠 처리하며, Tmux 세션으로 상시 운영했습니다.

<br>

## 참고

- 발음 가이드 영상과 테스트용 녹음 파일은 용량·개인정보 문제로 저장소에서 제외했습니다.
- `.env`는 저장소에 포함되지 않습니다. `.env.example`을 참고해 직접 작성해야 합니다.
