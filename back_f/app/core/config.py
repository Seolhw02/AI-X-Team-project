# core/config.py
# 이미지 가이드와 관련된 설정을 담고 있습니다.

PRONUNCIATION_GUIDES = [
    {"chars": ["ㄱ", "ㄲ", "ㅋ", "ㅇ"], "imageFile": "c-g.png"},
    {"chars": ["ㄴ", "ㄷ", "ㄸ", "ㅌ"], "imageFile": "c-n.png"},
    {"chars": ["ㄹ"], "imageFile": "c-r.png"},
    {"chars": ["ㅁ", "ㅂ", "ㅃ", "ㅍ"], "imageFile": "c-m.png"},
    {"chars": ["ㅅ", "ㅆ", "ㅈ", "ㅉ", "ㅊ"], "imageFile": "c-s.png"},
    {"chars": ["변이음_ㅅ", "변이음_ㅆ"], "imageFile": "c-s-alt.png"},
    {"chars": ["ㅏ"], "imageFile": "v-a.png"},
    {"chars": ["ㅔ", "ㅐ"], "imageFile": "v-e.png"},
    {"chars": ["ㅓ", "ㅗ"], "imageFile": "v-eo.png"},
    {"chars": ["ㅣ", "ㅑ", 'ㅒ', "ㅕ", "ㅖ", "ㅛ", "ㅠ"], "imageFile": "v-i.png"},
    {"chars": ["ㅡ", "ㅜ", "ㅘ", "ㅙ", "ㅚ", "ㅝ", "ㅞ", "ㅟ", "ㅢ"], "imageFile": "v-u.png"}
]
IMAGE_GUIDE_MAP = {char: guide["imageFile"] for guide in PRONUNCIATION_GUIDES for char in guide["chars"]}