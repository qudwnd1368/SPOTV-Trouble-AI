import hashlib
import json
import logging
import math
import os
import re
from collections import Counter


logger = logging.getLogger(__name__)

ALIASES = {
    "안먹어": "반응하지않음", "안 먹어": "반응하지않음", "안돼": "불량",
    "안 돼": "불량", "안나와": "출력불량", "안 나와": "출력불량",
    "인풋": "입력", "input": "입력", "신호없어": "입력불량", "신호 없어": "입력불량",
    "화면": "영상", "첫화면": "첫프레임", "vcr": "소재", "소리": "오디오",
    "계속나가": "송출", "계속 나가": "송출", "빨간 불": "빨간불",
    "xt2": "evs xt-2", "xt-2": "evs xt-2", "cl 3": "cl3",
}


def normalize(text):
    value = text.lower().strip()
    for old, new in ALIASES.items():
        value = value.replace(old, new)
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


def incident_text(item):
    return f"{item.equipment} {item.symptom} {item.cause} {item.action} {item.notes}"


def local_search(query, incidents, limit=3):
    q = local_vector(query)
    scored = [(cosine(q, local_vector(incident_text(item))), item) for item in incidents]
    return sorted(scored, key=lambda x: x[0], reverse=True)[:limit]


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
        logger.exception("Failed to create OpenAI embedding; saving incident without embedding.")
        return None


def semantic_search(query, incidents, limit=3):
    client = get_openai_client()
    if client and all(i.embedding for i in incidents):
        try:
            q = client.embeddings.create(model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"), input=query).data[0].embedding
            def dense_cos(raw):
                v = json.loads(raw)
                return sum(x*y for x, y in zip(q, v)) / (math.sqrt(sum(x*x for x in q))*math.sqrt(sum(y*y for y in v)))
            return sorted([(dense_cos(i.embedding), i) for i in incidents], key=lambda x: x[0], reverse=True)[:limit]
        except Exception:
            logger.exception("OpenAI semantic search failed; falling back to local search.")
    return local_search(query, incidents, limit)


def relevance_label(score, rank):
    if rank == 0 and score >= 0.30: return "매우 관련 높음"
    if score >= 0.16: return "관련 높음"
    return "참고 가능"


def is_ambiguous(query):
    return len(normalize(query)) <= 6 or not any(word in query.lower() for word in ["입력", "출력", "버튼", "오디오", "소리", "페이더", "화면", "신호", "재생", "녹화", "빨간"])
