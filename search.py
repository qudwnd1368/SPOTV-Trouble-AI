import json
import logging
import math
import os
import re
from collections import Counter


logger = logging.getLogger(__name__)
LOCAL_MIN_RELEVANCE_SCORE = float(os.getenv("LOCAL_MIN_RELEVANCE_SCORE", os.getenv("MIN_RELEVANCE_SCORE", "0.08")))
SEMANTIC_MIN_RELEVANCE_SCORE = float(os.getenv("SEMANTIC_MIN_RELEVANCE_SCORE", "0.35"))

ALIASES = {
    "안먹어": "반응하지않음", "안 먹어": "반응하지않음", "안돼": "불량",
    "안 돼": "불량", "안나와": "출력불량", "안 나와": "출력불량",
    "안나옴": "출력불량", "안 나옴": "출력불량", "안나온": "출력불량",
    "인풋": "입력", "input": "입력", "신호없어": "입력불량", "신호 없어": "입력불량",
    "화면": "영상", "첫화면": "첫프레임", "vcr": "소재", "소리": "오디오",
    "계속나가": "송출", "계속 나가": "송출", "빨간 불": "빨간불",
    "xt2": "evs xt-2", "xt-2": "evs xt-2", "cl 3": "cl3",
}


def canonical_text(text):
    value = text.lower().strip()
    for old, new in sorted(ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        value = value.replace(old, new)
    return value


def normalize(text):
    value = canonical_text(text)
    return re.sub(r"[^0-9a-z가-힣]+", "", value)


def local_vector(text):
    text = normalize(text)
    grams = [text[i:i+n] for n in (2, 3) for i in range(max(0, len(text)-n+1))]
    return Counter(grams)


def cosine(a, b):
    common = set(a) & set(b)
    numerator = sum(a[k] * b[k] for k in common)
    denominator = math.sqrt(sum(v*v for v in a.values()) * sum(v*v for v in b.values()))
    return numerator / denominator if denominator else 0.0


def knowledge_text(item):
    return f"{item.title} {item.context} {item.action} {item.caution}"


def keywords(text):
    return {
        normalized
        for token in re.findall(r"[0-9a-z가-힣]+", canonical_text(text))
        if len(normalized := normalize(token)) >= 2
    }


def lexical_score(query, item):
    q = local_vector(query)
    whole_score = cosine(q, local_vector(knowledge_text(item)))
    field_scores = [
        2.2 * cosine(q, local_vector(item.title)),
        1.7 * cosine(q, local_vector(item.context)),
        1.0 * cosine(q, local_vector(item.action)),
        0.9 * cosine(q, local_vector(item.caution)),
    ]

    q_terms = keywords(query)
    field_terms = [
        (normalize(item.title), 0.28),
        (normalize(item.context), 0.18),
        (normalize(item.action), 0.08),
        (normalize(item.caution), 0.06),
    ]
    keyword_bonus = sum(weight for term in q_terms for field, weight in field_terms if term in field)
    exact_bonus = 0.35 if normalize(query) and normalize(query) in normalize(knowledge_text(item)) else 0.0
    return whole_score * 0.7 + max(field_scores, default=0.0) + keyword_bonus + exact_bonus


def local_search(query, items, limit=3):
    scored = [(lexical_score(query, item), item) for item in items]
    return [result for result in sorted(scored, key=lambda x: x[0], reverse=True) if result[0] >= LOCAL_MIN_RELEVANCE_SCORE][:limit]


def get_openai_client():
    if not os.getenv("OPENAI_API_KEY"):
        return None
    try:
        from openai import OpenAI
        return OpenAI()
    except Exception as exc:
        logger.warning("OpenAI client is unavailable; local search will be used: %s", exc)
        return None


def create_embedding(text):
    client = get_openai_client()
    if not client:
        return None
    try:
        response = client.embeddings.create(model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"), input=text)
        return json.dumps(response.data[0].embedding)
    except Exception:
        logger.exception("Failed to create OpenAI embedding; saving knowledge item without embedding.")
        return None


def create_knowledge_embedding(data):
    return create_embedding(" ".join([data["title"], data["context"], data["action"], data["caution"]]))


def semantic_search(query, items, limit=3):
    client = get_openai_client()
    if client and items and all(item.embedding for item in items):
        try:
            q = client.embeddings.create(model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"), input=query).data[0].embedding
            def dense_cos(raw):
                v = json.loads(raw)
                return sum(x*y for x, y in zip(q, v)) / (math.sqrt(sum(x*x for x in q))*math.sqrt(sum(y*y for y in v)))
            scored = [
                (dense_cos(item.embedding) * 0.65 + lexical_score(query, item) * 0.75, item)
                for item in items
            ]
            return [result for result in sorted(scored, key=lambda x: x[0], reverse=True) if result[0] >= SEMANTIC_MIN_RELEVANCE_SCORE][:limit]
        except Exception:
            logger.exception("OpenAI semantic search failed; falling back to local search.")
    return local_search(query, items, limit)


def relevance_label(score, rank):
    if rank == 0 and score >= 0.30: return "매우 관련 높음"
    if score >= 0.16: return "관련 높음"
    return "참고 가능"
