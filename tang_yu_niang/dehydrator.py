"""本地关键词提取 + 情感分析（无需 API）"""
import re

STOPWORDS = {'的','了','在','是','我','你','他','她','它','们','这','那','也','都','和','与','但','就','不','没','有','吗','吧','啊','哦','嗯','呢'}

POSITIVE = {'开心','快乐','喜欢','爱','温柔','甜','棒','心动','感动','幸福','美好','可爱','珍贵','温暖','治愈','笑','哈哈'}
NEGATIVE = {'难过','伤心','哭','痛','难受','失望','委屈','生气','烦','累','焦虑','担心','害怕','后悔','讨厌','孤独'}
HIGH_AROUSAL = {'激动','兴奋','愤怒','紧张','害怕','心跳','颤抖','崩溃'}

MOOD_MAP = {
    '开心': ('😊', 0.8, 0.6), '心动': ('💗', 0.9, 0.8),
    '难过': ('🌧️', -0.6, 0.5), '生气': ('😤', -0.5, 0.8),
    '平静': ('🌿', 0.2, 0.2), '感动': ('🥺', 0.7, 0.6),
    '搞笑': ('😂', 0.7, 0.7), '温柔': ('🌸', 0.7, 0.3),
    '愧疚': ('😔', -0.3, 0.4), '复杂': ('🌀', 0.0, 0.5),
    '警醒': ('⚡', 0.1, 0.7),
}


def extract_keywords(text, max_keywords=8):
    """简单关键词提取"""
    freq = {}
    for length in (2, 3, 4):
        for i in range(len(text) - length + 1):
            sub = text[i:i+length]
            if re.match(r'^[一-鿿]+$', sub) and sub not in STOPWORDS:
                freq[sub] = freq.get(sub, 0) + 1
    sorted_words = sorted(freq.items(), key=lambda x: (-x[1], -len(x[0])))
    return [w for w, _ in sorted_words[:max_keywords]]


def estimate_emotion(text, mood_hint=None):
    """估算情感坐标"""
    if mood_hint and mood_hint in MOOD_MAP:
        emoji, val, ar = MOOD_MAP[mood_hint]
        return {'valence': val, 'arousal': ar, 'mood_label': mood_hint, 'mood_emoji': emoji}

    pos = sum(1 for w in POSITIVE if w in text)
    neg = sum(1 for w in NEGATIVE if w in text)
    high = sum(1 for w in HIGH_AROUSAL if w in text)
    total = pos + neg or 1
    valence = (pos - neg) / total * 0.8
    arousal = min(0.3 + high * 0.2 + total * 0.05, 1.0)

    if valence > 0.5:
        label, emoji = '开心', '😊'
    elif valence > 0.2:
        label, emoji = '温柔', '🌸'
    elif valence > -0.2:
        label, emoji = '平静', '🌿'
    else:
        label, emoji = '难过', '🌧️'

    return {'valence': round(valence, 2), 'arousal': round(arousal, 2),
            'mood_label': label, 'mood_emoji': emoji}
