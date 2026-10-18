import json
import os
import re
from collections import Counter
from datetime import datetime, timedelta, timezone

import requests

from personalization import get_supabase, validate_user_id

APIYI_URL = "https://api.apiyi.com/v1/chat/completions"
APIYI_MODEL = os.getenv("APIYI_MODEL", "gemini-3.1-flash-lite")
APIYI_API_KEY = os.getenv("APIYI_API_KEY", "")
GENERATION_THRESHOLD = 3
RECOMMENDATION_COUNT = 5
DEFAULT_THEMES = [
    "Office Lunches", "Exam Stress", "Group Projects",
    "Dating Apps", "Debugging", "Family Gatherings",
]
BROAD_THEMES = {"work", "relationships", "life", "tech", "surprise me", "custom theme"}


def _clean_name(theme, custom_theme=""):
    name = (custom_theme or "").strip() if theme == "Custom Theme" else (theme or "").strip()
    return name[:80]


def get_theme_history(user_id: str) -> list:
    user_id = validate_user_id(user_id)
    response = (get_supabase().table("theme_history")
                .select("theme,custom_theme,action,created_at")
                .eq("user_id", user_id).order("created_at", desc=True)
                .limit(200).execute())
    return response.data or []


def get_generation_count(history: list) -> int:
    return sum(1 for event in history if event.get("action") == "generated")


def get_trending_themes(limit: int = 6) -> list:
    db = get_supabase()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    response = (db.table("theme_history")
                .select("theme,custom_theme,action,user_id")
                .gte("created_at", cutoff).limit(5000).execute())
    scores = Counter()
    canonical = {}
    seen = set()
    weights = {"selected": 1, "generated": 2, "sticker_created": 3, "downloaded": 4}
    for event in response.data or []:
        name = _clean_name(event.get("theme"), event.get("custom_theme"))
        if not name or name.casefold() in BROAD_THEMES:
            continue
        normalized = name.casefold()
        key = (event.get("user_id"), normalized, event.get("action"))
        if key in seen:
            continue
        seen.add(key)
        canonical.setdefault(normalized, name)
        scores[normalized] += weights.get(event.get("action"), 1)

    trending = [canonical[key] for key, _ in scores.most_common(limit)]
    existing = {name.casefold() for name in trending}
    try:
        starter = (db.table("starter_themes").select("theme")
                   .eq("active", True).limit(30).execute())
        starters = [row.get("theme", "") for row in (starter.data or [])]
    except Exception:
        starters = []
    for name in starters + DEFAULT_THEMES:
        name = str(name).strip()
        if name and name.casefold() not in existing and name.casefold() not in BROAD_THEMES:
            trending.append(name)
            existing.add(name.casefold())
        if len(trending) >= limit:
            break
    return trending[:limit]


def get_cached_recommendations(user_id: str):
    response = (get_supabase().table("theme_recommendations")
                .select("suggestions,generation_count")
                .eq("user_id", validate_user_id(user_id)).limit(1).execute())
    return response.data[0] if response.data else None


def generate_ai_themes(history: list) -> list:
    if not APIYI_API_KEY:
        raise RuntimeError("APIYI_API_KEY is missing.")
    recent = history[:60]
    weights = {"selected": 1, "generated": 2, "sticker_created": 3, "downloaded": 4}
    interests = Counter()
    for event in recent:
        name = _clean_name(event.get("theme"), event.get("custom_theme"))
        if name and name.casefold() != "surprise me":
            interests[name] += weights.get(event.get("action"), 1)
    theme_names = [name for name, _ in interests.most_common(20)]
    prompt = f"""You recommend TOPICS for a meme-making app called Meme-it.
These are clickable subject areas, NOT meme captions, punchlines, jokes, or sentences.

USER INTERESTS (ordered by engagement):
{json.dumps(theme_names, ensure_ascii=False)}

Return exactly five fresh, relevant, varied meme TOPICS.
- Four should be inspired by the user's interests; one can explore an adjacent interest.
 - Expand broad categories into different aspects: Work -> Office Lunches, Team Projects, Internships, Meetings; University -> Exams, Campus Food, Group Projects.
 - Topics should be short noun phrases, 1 to 4 words each.
 - Never write caption-like phrases beginning with 'When', 'POV', 'Me', or 'That moment'.
 - Avoid exact repeats of previous topics, generic categories, and duplicates.
 - Keep topics safe and general-audience friendly.
Return only valid JSON: {{"themes": ["Topic 1", "Topic 2", "Topic 3", "Topic 4", "Topic 5"]}}"""
    response = requests.post(
        APIYI_URL,
        headers={"Authorization": f"Bearer {APIYI_API_KEY}", "Content-Type": "application/json"},
        json={"model": APIYI_MODEL, "messages": [{"role": "user", "content": prompt}],
              "temperature": 0.8, "max_tokens": 500},
        timeout=(10, 45),
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    if isinstance(content, list):
        content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.IGNORECASE)
    themes = json.loads(content).get("themes")
    if not isinstance(themes, list) or len(themes) != RECOMMENDATION_COUNT:
        raise ValueError("AI did not return five themes.")
    cleaned = []
    previous = {name.casefold() for name in theme_names}
    for item in themes:
        if not isinstance(item, str):
            raise ValueError("Invalid AI theme.")
        name = item.strip()
        if (not name or len(name) > 60 or len(name.split()) > 5
                or name.casefold() in previous
                or name.casefold() in {x.casefold() for x in cleaned}
                or name.casefold() in BROAD_THEMES
                or re.match(r"^(when|pov|me|that moment)\b", name, re.I)):
            raise ValueError("AI returned a duplicate or caption-like topic.")
        cleaned.append(name)
    return cleaned


def get_recommendations(user_id: str, refresh: bool = False) -> dict:
    user_id = validate_user_id(user_id)
    history = get_theme_history(user_id)
    count = get_generation_count(history)
    trending = get_trending_themes()
    result = {
        "type": "trending" if count < GENERATION_THRESHOLD else "personalized",
        "generation_count": count,
        "next_unlock": max(0, GENERATION_THRESHOLD - count),
        "trending_themes": trending,
        "personalized_themes": [],
        "themes": trending,  # Backward-compatible for older frontend
    }
    if count < GENERATION_THRESHOLD:
        return result

    cached = get_cached_recommendations(user_id)
    if cached and not refresh and count - int(cached["generation_count"]) < GENERATION_THRESHOLD:
        themes = cached.get("suggestions") or []
        result.update({"cached": True, "personalized_themes": themes, "themes": themes})
        return result

    themes = generate_ai_themes(history)
    (get_supabase().table("theme_recommendations").upsert(
        {"user_id": user_id, "suggestions": themes, "generation_count": count,
         "created_at": datetime.now(timezone.utc).isoformat()},
        on_conflict="user_id").execute())
    result.update({"cached": False, "personalized_themes": themes, "themes": themes})
    return result
