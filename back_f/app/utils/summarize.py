from openai import OpenAI
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def summarize_feedback_with_gpt(feedback_list: list[dict]) -> str:
    """
    여러 개의 피드백 dict를 받아 GPT로 요약한 문자열을 생성합니다.
    feedback_list: [{score: int, mouth_feedback: str, tongue_position_feedback: str, ...}, ...]
    하나의 문단으로 자연스럽게 요약해 주세요.
    절대로 번호나 기호를 사용하지 말고, '입 모양', '혀 위치', '호흡', '학습 포인트' 등을 이어지는 설명문처럼 서술하세요.
    """
    # 모든 피드백을 문자열로 합침
    feedback_texts = []
    for f in feedback_list:
        feedback_texts.append(
            f"""
            [점수] {f.get("score")}
            [입 모양] {f.get("mouth_feedback")}
            [혀 위치] {f.get("tongue_position_feedback")}
            [호흡] {f.get("breathing_feedback")}
            [학습 포인트] {f.get("teaching_point")}
            """
        )

    merged_text = "\n".join(feedback_texts)

    prompt = f"""
    아래 발음 피드백들을 읽고, 학습자가 이해하기 쉽게 핵심 요약만 만들어줘.
    중복된 내용은 합치고, 중요한 교정 포인트는 구체적으로 유지해줘.
    
    === 피드백 원문 ===
    {merged_text}
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "너는 영어 발음 교정 선생님이다."},
                      {"role": "user", "content": prompt}],
            max_tokens=400,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[GPT 요약 오류] {e}")
        return "피드백 요약 생성 실패"