
import os
import uuid
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from supabase import Client, create_client

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

STANDARD_THEMES = {
    "Work",
    "Relationships",
    "Life",
    "Tech",
    "Surprise Me",
    "Custom Theme",
}

ACTION_WEIGHTS = {
    "selected": 1,
    "generated": 2,
    "sticker_created": 3,
    "downloaded": 4,
}


@lru_cache(maxsize=1)
def get_supabase() -> Client:
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_KEY", "").strip()

    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL or SUPABASE_KEY is missing."
        )

    return create_client(url, key)


def validate_user_id(user_id: str) -> str:
    try:
        return str(uuid.UUID(str(user_id)))
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Invalid anonymous user ID.")


def register_user(user_id: str) -> dict:
    user_id = validate_user_id(user_id)
    db = get_supabase()

    db.table("meme_users").upsert(
        {"id": user_id},
        on_conflict="id",
    ).execute()

    return {
        "user_id": user_id,
        "registered": True,
    }


def save_generated_memes(
    user_id: str,
    theme: str,
    custom_theme: str,
    memes: list,
    caption_style: str = "mixed",
) -> list:
    user_id = validate_user_id(user_id)

    if theme not in STANDARD_THEMES:
        raise ValueError("Invalid theme.")

    register_user(user_id)

    rows = []

    for meme in memes:
        caption = str(meme.get("caption", "")).strip()

        if not caption:
            continue

        rows.append({
            "user_id": user_id,
            "caption": caption[:120],
            "theme": theme,
            "custom_theme": (
                custom_theme.strip()[:100]
                if theme == "Custom Theme"
                else None
            ),
            "caption_style": caption_style,
        })

    if not rows:
        return []

    response = (
        get_supabase()
        .table("generated_memes")
        .insert(rows)
        .execute()
    )

    return response.data or []


def record_meme_feedback(
    user_id: str,
    meme_id: str,
    action: str,
) -> dict:
    user_id = validate_user_id(user_id)

    if action not in {
        "selected",
        "liked",
        "disliked",
        "sticker_created",
    }:
        raise ValueError("Invalid feedback action.")

    meme_id = str(uuid.UUID(str(meme_id)))

    db = get_supabase()
    register_user(user_id)

    # Ensure feedback belongs to this user's meme.
    result = (
        db.table("generated_memes")
        .select("id")
        .eq("id", meme_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )

    if not result.data:
        raise ValueError("Meme not found for this user.")

    response = (
        db.table("meme_feedback")
        .insert({
            "user_id": user_id,
            "meme_id": meme_id,
            "action": action,
        })
        .execute()
    )

    return {
        "saved": True,
        "feedback": response.data or [],
    }


def record_theme_event(
    user_id: str,
    theme: str,
    custom_theme: str = "",
    action: str = "generated",
) -> dict:
    user_id = validate_user_id(user_id)

    if theme not in STANDARD_THEMES:
        raise ValueError("Invalid theme.")

    if action not in ACTION_WEIGHTS:
        raise ValueError("Invalid theme action.")

    custom_theme = custom_theme.strip()

    if theme == "Custom Theme" and not custom_theme:
        raise ValueError("Custom theme cannot be empty.")

    if len(custom_theme) > 100:
        raise ValueError(
            "Custom theme must be 100 characters or fewer."
        )

    register_user(user_id)

    response = (
        get_supabase()
        .table("theme_history")
        .insert({
            "user_id": user_id,
            "theme": theme,
            "custom_theme": (
                custom_theme
                if theme == "Custom Theme"
                else None
            ),
            "action": action,
        })
        .execute()
    )

    return {
        "saved": True,
        "event": response.data or [],
    }


def get_theme_suggestions(
    user_id: str,
    limit: int = 5,
) -> dict:
    user_id = validate_user_id(user_id)
    limit = max(1, min(limit, 5))

    response = (
        get_supabase()
        .table("theme_history")
        .select("theme,custom_theme,action")
        .eq("user_id", user_id)
        .limit(1000)
        .execute()
    )

    scores = defaultdict(int)
    labels = {}

    for event in response.data or []:
        theme = event.get("theme", "")
        custom = (event.get("custom_theme") or "").strip()
        action = event.get("action", "selected")

        if theme == "Custom Theme":
            if not custom:
                continue

            key = "custom:" + custom.casefold()
            label = custom
            suggestion_type = "custom"
        else:
            if theme not in STANDARD_THEMES:
                continue

            key = "standard:" + theme
            label = theme
            suggestion_type = "standard"

        scores[key] += ACTION_WEIGHTS.get(action, 1)

        labels[key] = {
            "theme": label,
            "type": suggestion_type,
        }

    ranked = sorted(
        scores,
        key=lambda key: scores[key],
        reverse=True,
    )

    suggestions = []

    for key in ranked[:limit]:
        suggestions.append({
            **labels[key],
            "score": scores[key],
        })

    return {
        "user_id": user_id,
        "suggestions": suggestions,
    }


def get_user_preferences(user_id: str) -> dict:
    user_id = validate_user_id(user_id)

    response = (
        get_supabase()
        .table("user_preferences")
        .select(
            "preferred_style,preferred_humour"
        )
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )

    if response.data:
        return {
            "user_id": user_id,
            **response.data[0],
        }

    return {
        "user_id": user_id,
        "preferred_style": "mixed",
        "preferred_humour": None,
    }

    
# Compatibility functions for main.py

def ensure_user(user_id: str) -> str:
    result = register_user(user_id)
    return result["user_id"]


def save_generated(
    user_id: str,
    result: dict,
    theme: str,
    custom_theme: str = "",
) -> list[str]:
    saved = save_generated_memes(
        user_id=user_id,
        theme=theme,
        custom_theme=custom_theme,
        memes=result.get("memes", []),
    )
    return [row["id"] for row in saved]


def save_theme(
    user_id: str,
    theme: str,
    custom_theme: str = "",
    action: str = "generated",
) -> dict:
    return record_theme_event(
        user_id=user_id,
        theme=theme,
        custom_theme=custom_theme,
        action=action,
    )


def record_feedback(
    user_id: str,
    meme_id: str,
    action: str,
) -> dict:
    return record_meme_feedback(
        user_id=user_id,
        meme_id=meme_id,
        action=action,
    )


def suggest_themes(user_id: str) -> list[str]:
    # Return popular starter themes for new users.
    defaults = [
        "Life",
        "Work",
        "Relationships",
        "Tech",
        "Surprise Me",
    ]

    # The frontend expects a list of theme names.
    result = get_theme_suggestions(user_id)

    suggestions = [
        item["theme"]
        for item in result.get("suggestions", [])
        if isinstance(item.get("theme"), str)
    ]

    # Add defaults if there isn't enough user history.
    for theme in defaults:
        if theme not in suggestions:
            suggestions.append(theme)

        if len(suggestions) >= 5:
            break

    return suggestions[:5]

