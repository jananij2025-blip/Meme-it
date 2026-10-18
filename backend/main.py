



import base64



import hashlib



import json



import os



import secrets



import sqlite3



import threading







from io import BytesIO



from pathlib import Path

from typing import Optional

from pydantic import BaseModel

import personalization as personalization_db







import requests



from dotenv import load_dotenv



from fastapi import FastAPI, File, Form, HTTPException, UploadFile



from fastapi.middleware.cors import CORSMiddleware



from fastapi.responses import StreamingResponse



from PIL import Image, ImageOps, UnidentifiedImageError















# ============================================================
# CONFIGURATION
# ============================================================
BASE_DIR = Path(__file__).resolve().parent



load_dotenv(BASE_DIR / ".env")







APIYI_API_KEY = os.getenv("APIYI_API_KEY", "").strip()







APIYI_MODEL = os.getenv(



    "APIYI_MODEL",



    "gemini-3.1-flash-lite",



).strip()







APIYI_URL = "https://api.apiyi.com/v1/chat/completions"







MAX_FILE_SIZE = 10 * 1024 * 1024



MAX_PIXELS = 20_000_000







ALLOWED_TYPES = {



    "image/jpeg",



    "image/png",



    "image/webp",



}







THEMES = {



    "Work",



    "Relationships",



    "Life",



    "Tech",



    "Surprise Me",



    "Custom Theme",



}







# Development allowance, NOT a provider billing limit.
BUDGET_USD = 0.50



RESERVATION_PER_REQUEST = 0.01







DB_PATH = BASE_DIR / "caption_cache.sqlite3"







# Changing this separates new results from old cache entries.
PROMPT_VERSION = "photo-first-v7"







# Maximum provider calls for one fresh generation.
MAX_GENERATION_ATTEMPTS = 2







db_lock = threading.Lock()











# ============================================================
# FASTAPI
# ============================================================
app = FastAPI(



    title="Meme-it API",



    version="0.8.0",



)







app.add_middleware(



    CORSMiddleware,



allow_origins=[
    "http://localhost:5173",
    "http://localhost:5174",
    "https://meme-it-beta.vercel.app",
    "https://meme-jl0tvagdc-janani-7253.vercel.app",
],


    allow_credentials=False,



    allow_methods=["GET", "POST"],



    allow_headers=["*"],



)











# ============================================================
# DATABASE
# ============================================================
def init_db():



    with sqlite3.connect(DB_PATH) as db:



        db.execute("""



            CREATE TABLE IF NOT EXISTS captions (



                cache_key TEXT PRIMARY KEY,



                captions_json TEXT NOT NULL



            )



        """)







        db.execute("""



            CREATE TABLE IF NOT EXISTS spending (



                id INTEGER PRIMARY KEY CHECK (id = 1),



                reserved_usd REAL NOT NULL DEFAULT 0



            )



        """)







        db.execute("""



            INSERT OR IGNORE INTO spending



            (id, reserved_usd)



            VALUES (1, 0)



        """)







        # NEW: Remember captions previously generated
        # for each photo and theme.
        db.execute("""



            CREATE TABLE IF NOT EXISTS caption_history (



                cache_key TEXT NOT NULL,



                caption_normalized TEXT NOT NULL,



                caption_text TEXT NOT NULL,



                PRIMARY KEY (



                    cache_key,



                    caption_normalized



                )



            )



        """)











init_db()











def reserve_budget():



    with db_lock:



        with sqlite3.connect(DB_PATH) as db:



            current = db.execute(



                """



                SELECT reserved_usd



                FROM spending



                WHERE id = 1



                """



            ).fetchone()[0]







            if (



                current + RESERVATION_PER_REQUEST



                > BUDGET_USD + 1e-9



            ):



                raise HTTPException(



                    status_code=429,



                    detail=(



                        "Development AI request limit reached. "



                        "Check your spending allowance."



                    ),



                )







            db.execute(



                """



                UPDATE spending



                SET reserved_usd = ?



                WHERE id = 1



                """,



                (



                    current + RESERVATION_PER_REQUEST,



                ),



            )











def get_cached_result(key):



    with sqlite3.connect(DB_PATH) as db:



        row = db.execute(



            """



            SELECT captions_json



            FROM captions



            WHERE cache_key = ?



            """,



            (key,),



        ).fetchone()







    if row is None:



        return None







    try:



        result = json.loads(row[0])







        if (



            isinstance(result, dict)



            and isinstance(result.get("people_count"), int)



            and isinstance(result.get("people"), list)



            and isinstance(result.get("memes"), list)



            and len(result["memes"]) == 5



            and isinstance(result.get("captions"), list)



            and len(result["captions"]) == 5



        ):



            return result







    except (ValueError, TypeError):



        pass







    return None











def normalize_caption(caption):



    return " ".join(caption.casefold().split())











def get_caption_history(key):



    with sqlite3.connect(DB_PATH) as db:



        rows = db.execute(



            """



            SELECT caption_text



            FROM caption_history



            WHERE cache_key = ?



            ORDER BY rowid DESC



            LIMIT 100



            """,



            (key,),



        ).fetchall()







    return [row[0] for row in rows]











def save_cached_result(key, result):



    with db_lock:



        with sqlite3.connect(DB_PATH) as db:



            db.execute(



                """



                INSERT OR REPLACE INTO captions



                (cache_key, captions_json)



                VALUES (?, ?)



                """,



                (key, json.dumps(result)),



            )







            for caption in result["captions"]:



                db.execute(



                    """



                    INSERT OR IGNORE INTO caption_history



                    (



                        cache_key,



                        caption_normalized,



                        caption_text



                    )



                    VALUES (?, ?, ?)



                    """,



                    (



                        key,



                        normalize_caption(caption),



                        caption,



                    ),



                )











# ============================================================
# IMAGE HANDLING
# ============================================================












async def load_image(file: UploadFile):



    if file.content_type not in ALLOWED_TYPES:



        raise HTTPException(



            status_code=400,



            detail="Only JPG, PNG and WebP images are supported.",



        )







    data = await file.read(MAX_FILE_SIZE + 1)







    if len(data) > MAX_FILE_SIZE:



        raise HTTPException(



            status_code=413,



            detail="Maximum image size is 10 MB.",



        )







    try:



        with Image.open(BytesIO(data)) as source:



            if source.width * source.height > MAX_PIXELS:



                raise HTTPException(



                    status_code=413,



                    detail="Image dimensions are too large.",



                )







            image = ImageOps.exif_transpose(



                source



            ).convert("RGBA")







            image.thumbnail((1024, 1024))







            return image.copy()







    except (



        UnidentifiedImageError,



        OSError,



        ValueError,



        Image.DecompressionBombError,



    ):



        raise HTTPException(



            status_code=400,



            detail="Invalid image file.",



        )











def png_response(image):



    output = BytesIO()



    image.save(output, format="PNG")



    output.seek(0)







    return StreamingResponse(



        output,



        media_type="image/png",



        headers={



            "Cache-Control": "no-store",



        },



    )











def prepare_ai_image(image):



    rgb = image.convert("RGB")



    rgb.thumbnail((512, 512))







    output = BytesIO()



    rgb.save(



        output,



        format="JPEG",



        quality=75,



    )







    return output.getvalue()











def create_cache_key(



    image_bytes,



    theme,



    custom_theme,



):



    digest = hashlib.sha256()







    for part in (



        PROMPT_VERSION.encode(),



        image_bytes,



        APIYI_MODEL.encode(),



        theme.encode(),



        custom_theme.encode(),



    ):



        digest.update(part)



        digest.update(b"\x00")







    return digest.hexdigest()











# ============================================================
# FRESH MEME PROMPTS
# ============================================================
CREATIVE_DIRECTIONS = {



    "Work": [



        "office politics and subtle sarcasm",



        "meetings that should have been emails",



        "coworker chaos and workplace misunderstandings",



        "managers, deadlines and ridiculous expectations",



        "corporate nonsense and painfully relatable situations",



        "interns, HR and awkward office conversations",



    ],



    "Relationships": [



        "dating misunderstandings and mixed signals",



        "couple arguments over tiny things",



        "crushes, texting and overthinking",



        "relationship expectations versus reality",



        "jealousy, dramatic reactions and awkward romance",



    ],



    "Life": [



        "adulting failures and everyday chaos",



        "money problems and bad decisions",



        "social awkwardness and unexpected situations",



        "sleep, procrastination and unrealistic plans",



        "family situations and relatable struggles",



    ],



    "Tech": [



        "programming bugs and debugging disasters",



        "group projects and impossible deadlines",



        "software updates and technical frustration",



        "developers, users and absurd requirements",



        "Wi-Fi problems and technology betrayal",



    ],



}











def get_creative_direction(theme, custom_theme):



    selected_theme = (



        custom_theme



        if theme == "Custom Theme"



        else theme



    )







    directions = CREATIVE_DIRECTIONS.get(theme)







    if not directions:



        directions = [



            f"unexpected funny situations about {selected_theme}",



            f"relatable everyday struggles involving {selected_theme}",



            f"absurd misunderstandings related to {selected_theme}",



            f"clever ironic twists involving {selected_theme}",



        ]







    return secrets.choice(directions)











def build_prompt(



    theme,



    custom_theme,



    previous_captions=None,



    fresh=False,



):



    selected_theme = (



        custom_theme



        if theme == "Custom Theme"



        else theme



    )







    direction = get_creative_direction(



        theme,



        custom_theme,



    )







    previous_captions = previous_captions or []







    previous_section = ""







    if previous_captions:



        previous_list = "\n".join(



            f"- {caption}"



            for caption in previous_captions[-60:]



        )







        previous_section = f"""



PREVIOUSLY GENERATED CAPTIONS:







{previous_list}







IMPORTANT:



These captions have already been shown to the user.







Do not repeat any of them.



Do not merely change one or two words.



Create new joke situations, setups and punchlines.



"""







    fresh_instruction = ""







    if fresh:



        fresh_instruction = """



THIS IS A FRESH GENERATION REQUEST.







The user pressed the generate button again.







They expect five NEW meme ideas.







Do not reuse familiar joke templates.



Try surprising setups and punchlines.



"""







    return f"""



You are the comedy writer and fictional character



casting director for Meme-it, a reaction sticker maker.







Analyze the uploaded photo carefully.







SELECTED COMEDY THEME:



{selected_theme}







CREATIVE DIRECTION:



{direction}







{fresh_instruction}







{previous_section}







1. PEOPLE DETECTION







Count visible human people in the image.







Do not count animals or faces printed on objects.







For each person, estimate the center of their face



using normalized coordinates:







x = 0 at left, 1 at right.



y = 0 at top, 1 at bottom.







Sort people from left to right.



Assign person_index beginning at 1.







For 1 to 5 people, include everyone.







For 6 or more people, select 2 to 5 important people



but report the approximate total in people_count.







If no people are visible, return an empty people list.







2. FUNNY MEMES







Generate EXACTLY FIVE funny and DISTINCT captions.







Every caption must be 120 characters or fewer.







Make each caption a different joke.







Use varied formats such as:







- POV humour



- Relatable situations



- Unexpected twists



- Sarcasm



- Awkward misunderstandings



- Funny fictional conversations



- Expectations versus reality



- Absurd but relatable situations








Every caption must match BOTH the uploaded photo
and the selected theme.

PHOTO-FIRST RULE (VERY IMPORTANT):
Before writing captions, identify the most obvious
visible facial expressions, body language, poses,
and interactions in the uploaded photo.

Use those visual details as the foundation
of every joke.

The selected theme provides the situation or
context, but the person's visible reaction must
make sense as the punchline.

For example:
- Screaming face: shock, panic, outrage, excitement.
- Crying face: sadness, dramatic disappointment.
- Laughing face: uncontrollable amusement.
- Confused face: disbelief, misunderstanding.
- Blank stare: awkward silence, disbelief, exhaustion.

These are examples only. Always analyze the
actual uploaded photo.

If the selected theme is a fictional universe,
use recognizable situations from that universe,
but make the visible reaction essential to the joke.

Avoid random character references, complicated
lore, or jokes that would work equally well
with an unrelated photo.

Prefer short, punchy, relatable captions.
Use natural meme language.

Do not produce generic image descriptions.
Do not make every caption begin with "Me when".

FINAL SELF-CHECK:
For each caption, ask:
"Does this joke make sense with the person's
actual expression or pose?"

If not, rewrite it before returning the JSON.








3. FICTIONAL CHARACTER LABELS







When there are multiple people, assign funny



fictional roles to the people.







Examples:







ME



MY BOSS



MY MANAGER



MY FRIEND



MY BESTIE



MY MOM



MY DAD



MY SIBLING



MY LECTURER



MY TEACHER



MY GROUPMATE



MY COWORKER



MY EX



MY CRUSH



THE CLIENT



THE INTERN



HR



MY BANK ACCOUNT



MY LAST BRAIN CELL







You may invent other funny, short labels.







Never use appearance or clothing as labels.







Bad examples:







SMILING PERSON



PERSON ON THE LEFT



CONFUSED GUY



THE RED SHIRT







4. CAST THE RIGHT FACE







Do not automatically assign ME to person 1.







Use expressions, poses and interactions



to choose which person fits each joke.







The same photo can have different role assignments



for each of the five memes.







All roles are fictional, not statements about



real relationships.







5. CHARACTERS







Every meme must contain its own characters array.







Each character contains:







- person_index



- label







Each label must be 28 characters or fewer.







For 2 to 5 people, assign a role to every person.







For 6 or more people, assign roles to all selected



people in the people array.







For 0 or 1 person, return characters: [].







Never assign two different roles to the same person



within one meme.







6. OUTPUT







Return ONLY valid JSON.







No Markdown.



No code fences.



No explanation.







Use this exact structure, but with EXACTLY FIVE memes:







{{



  "people_count": 2,



  "people": [



    {{



      "person_index": 1,



      "x": 0.25,



      "y": 0.32



    }},



    {{



      "person_index": 2,



      "x": 0.75,



      "y": 0.34



    }}



  ],



  "memes": [



    {{



      "caption": "When the deadline moves up but the salary doesn't",



      "characters": [



        {{



          "person_index": 1,



          "label": "MY MANAGER"



        }},



        {{



          "person_index": 2,



          "label": "ME"



        }}



      ]



    }}



  ]



}}







The example contains only one meme.







Your actual response MUST contain EXACTLY FIVE.







Do not copy the example caption.







Prioritize originality, humour, relatability



and clever fictional casting.



"""











# ============================================================
# RESPONSE VALIDATION
# ============================================================
def extract_json(content):



    if isinstance(content, list):



        content = "".join(



            part.get("text", "")



            for part in content



            if isinstance(part, dict)



        )







    if not isinstance(content, str):



        raise ValueError(



            "AI returned an unsupported response."



        )







    content = content.strip()







    if content.startswith("```"):



        content = (



            content.split("\n", 1)[-1]



            .rsplit("```", 1)[0]



            .strip()



        )







    return json.loads(content)











def validate_ai_result(parsed):



    if not isinstance(parsed, dict):



        raise ValueError(



            "AI response must be an object."



        )







    count = parsed.get("people_count")



    raw_people = parsed.get("people")



    raw_memes = parsed.get("memes")







    if type(count) is not int or not 0 <= count <= 100:



        raise ValueError("Invalid people_count.")







    if not isinstance(raw_people, list):



        raise ValueError("Invalid people array.")







    if (



        not isinstance(raw_memes, list)



        or len(raw_memes) != 5



    ):



        raise ValueError(



            "AI must return exactly five memes."



        )







    if count <= 5 and len(raw_people) != count:



        raise ValueError(



            "People count does not match people array."



        )







    if count > 5 and not 2 <= len(raw_people) <= 5:



        raise ValueError(



            "Invalid selected group size."



        )







    people = []



    seen_indices = set()







    for person in raw_people:



        if not isinstance(person, dict):



            raise ValueError("Invalid person entry.")







        index = person.get("person_index")



        x = person.get("x")



        y = person.get("y")







        if type(index) is not int or index < 1:



            raise ValueError("Invalid person index.")







        if index in seen_indices:



            raise ValueError("Duplicate person index.")







        if (



            type(x) not in (int, float)



            or type(y) not in (int, float)



            or not 0 <= x <= 1



            or not 0 <= y <= 1



        ):



            raise ValueError(



                "Invalid face coordinates."



            )







        seen_indices.add(index)







        people.append({



            "person_index": index,



            "x": float(x),



            "y": float(y),



        })







    people.sort(



        key=lambda person: person["x"]



    )







    valid_indices = {



        person["person_index"]



        for person in people



    }







    memes = []







    for meme in raw_memes:



        if not isinstance(meme, dict):



            raise ValueError("Invalid meme entry.")







        caption = meme.get("caption")



        raw_characters = meme.get("characters")







        if (



            not isinstance(caption, str)



            or not caption.strip()



            or len(caption.strip()) > 120



        ):



            raise ValueError("Invalid caption.")







        if not isinstance(raw_characters, list):



            raise ValueError(



                "Invalid characters array."



            )







        # Gemini sometimes adds role labels to single-person memes.
        # Ignore those labels rather than rejecting otherwise valid captions.
        if count <= 1:

            raw_characters = []



        characters = []



        used_indices = set()







        for character in raw_characters:



            if not isinstance(character, dict):



                raise ValueError(



                    "Invalid character entry."



                )







            index = character.get("person_index")



            label = character.get("label")







            if (



                type(index) is not int



                or index not in valid_indices



                or index in used_indices



            ):



                raise ValueError(



                    "Invalid character person_index."



                )







            if (



                not isinstance(label, str)



                or not label.strip()



                or len(label.strip()) > 28



            ):



                raise ValueError(



                    "Invalid character label."



                )







            used_indices.add(index)







            characters.append({



                "person_index": index,



                "label": label.strip().upper(),



            })







        if count > 1 and used_indices != valid_indices:



            raise ValueError(



                "Every selected person needs a role."



            )







        characters.sort(



            key=lambda character: character["person_index"]



        )







        memes.append({



            "caption": caption.strip(),



            "characters": characters,



        })







    captions = [



        meme["caption"]



        for meme in memes



    ]







    normalized = [



        normalize_caption(caption)



        for caption in captions



    ]







    if len(set(normalized)) != 5:



        raise ValueError(



            "AI generated duplicate captions."



        )







    return {



        "people_count": count,



        "people": people,



        "memes": memes,



        "captions": captions,



    }











# ============================================================
# BASIC ENDPOINTS
# ============================================================
@app.get("/")



def home():



    return {



        "message": "Meme-it backend is running!"



    }











@app.get("/health")



def health():



    return {



        "status": "ok",



        "model": APIYI_MODEL,



        "api_key_configured": bool(APIYI_API_KEY),



        "prompt_version": PROMPT_VERSION,



    }











# ============================================================
# IMAGE PREPARATION
# ============================================================
@app.post("/api/prepare-image")



async def prepare_image(



    file: UploadFile = File(...)



):



    return png_response(



        await load_image(file)



    )











# ============================================================
# BACKGROUND REMOVAL
# ============================================================












# ============================================================
# APIYI REQUEST
# ============================================================
def request_apiyi(



    image_bytes,



    theme,



    custom_theme,



    previous_captions,



    fresh,



):



    image_url = (



        "data:image/jpeg;base64,"



        + base64.b64encode(



            image_bytes



        ).decode("utf-8")



    )







    prompt = build_prompt(



        theme,



        custom_theme,



        previous_captions,



        fresh,



    )







    payload = {



        "model": APIYI_MODEL,



        "messages": [



            {



                "role": "user",



                "content": [



                    {



                        "type": "text",



                        "text": prompt,



                    },



                    {



                        "type": "image_url",



                        "image_url": {



                            "url": image_url,



                        },



                    },



                ],



            }



        ],



        "temperature": 1.0,



        "max_tokens": 2500,



    }







    try:



        response = requests.post(



            APIYI_URL,



            headers={



                "Authorization": (



                    f"Bearer {APIYI_API_KEY}"



                ),



                "Content-Type": "application/json",



            },



            json=payload,



            timeout=(10, 60),



        )







        if not response.ok:



            error_message = (



                f"APIYI returned HTTP "



                f"{response.status_code}."



            )







            try:



                provider_message = (



                    response.json()



                    .get("error", {})



                    .get("message", "")



                )







                if "无权使用模型" in provider_message:



                    error_message = (



                        "Your APIYI token cannot use model "



                        f"'{APIYI_MODEL}'. "



                        "Check model permissions."



                    )







                elif response.status_code == 401:



                    error_message = (



                        "APIYI authentication failed. "



                        "Check your API key."



                    )







                elif response.status_code == 429:



                    error_message = (



                        "APIYI rate limit or quota reached."



                    )







            except (



                ValueError,



                AttributeError,



                TypeError,



            ):



                pass







            raise HTTPException(



                status_code=502,



                detail=error_message,



            )







        result = response.json()



        choices = result.get("choices", [])







        if not choices:



            raise ValueError(



                "AI response did not contain any choices."



            )







        content = choices[0]["message"]["content"]



        parsed = extract_json(content)







        return validate_ai_result(parsed)







    except requests.Timeout:



        raise HTTPException(



            status_code=504,



            detail=(



                "APIYI took too long to respond. "



                "Please try again later."



            ),



        )







    except requests.RequestException as error:



        print(



            "APIYI connection error:",



            type(error).__name__,



            flush=True,



        )







        raise HTTPException(



            status_code=502,



            detail="Could not connect to APIYI.",



        )











# ============================================================
def add_personalization(result, user_id, theme, custom_theme):

    if not user_id:

        return result

    ids = personalization_db.save_generated(user_id, result, theme, custom_theme)

    personalization_db.save_theme(user_id, theme, custom_theme, 'generated')

    result['meme_ids'] = ids

    return result



class FeedbackRequest(BaseModel):

    user_id: str

    meme_id: str

    action: str



class ThemeEventRequest(BaseModel):

    user_id: str

    theme: str

    custom_theme: str = ''

    action: str = 'selected'



class PreferencesRequest(BaseModel):

    user_id: str

    preferred_style: str = 'mixed'

    preferred_humour: Optional[str] = None



@app.post('/api/users/{user_id}')

def register_user(user_id: str):

    return {'user_id': personalization_db.ensure_user(user_id)}



@app.get('/api/users/{user_id}/suggested-themes')

def suggested_themes(user_id: str):

    return {'suggestions': personalization_db.suggest_themes(user_id)}



@app.get("/api/ai-theme-recommendations/{user_id}")
def ai_theme_recommendations(user_id: str, refresh: bool = False):
    # Import here so backend/.env has already been loaded.
    from theme_recommender import get_recommendations

    try:
        return get_recommendations(user_id, refresh=refresh)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except requests.RequestException:
        raise HTTPException(status_code=502, detail="AI recommendation service unavailable.")


@app.get('/api/users/{user_id}/preferences')

def get_user_preferences(user_id: str):

    return personalization_db.get_preferences(user_id)



@app.post('/api/preferences')

def update_user_preferences(request: PreferencesRequest):

    return personalization_db.update_preferences(request.user_id, request.preferred_style, request.preferred_humour)



@app.post('/api/meme-feedback')

def meme_feedback(request: FeedbackRequest):

    personalization_db.record_feedback(request.user_id, request.meme_id, request.action)

    return {'ok': True}



@app.post('/api/theme-event')

def theme_event(request: ThemeEventRequest):

    personalization_db.save_theme(request.user_id, request.theme, request.custom_theme, request.action)

    return {'ok': True}



# AI CAPTION GENERATION
# ============================================================
@app.post("/api/generate-captions")



async def generate_captions(



    file: UploadFile = File(...),



    theme: str = Form(...),



    custom_theme: str = Form(""),



    fresh: bool = Form(False),

    user_id: Optional[str] = Form(None),



):



    if theme not in THEMES:



        raise HTTPException(



            status_code=400,



            detail="Invalid theme.",



        )







    custom_theme = custom_theme.strip()







    if theme == "Custom Theme" and not custom_theme:



        raise HTTPException(



            status_code=400,



            detail="Please enter a custom theme.",



        )







    if len(custom_theme) > 100:



        raise HTTPException(



            status_code=400,



            detail=(



                "Custom theme must be "



                "100 characters or fewer."



            ),



        )







    if not APIYI_API_KEY:



        raise HTTPException(



            status_code=503,



            detail=(



                "APIYI API key is missing "



                "from backend/.env."



            ),



        )







    image_bytes = prepare_ai_image(



        await load_image(file)



    )







    cache_key = create_cache_key(



        image_bytes,



        theme,



        custom_theme,



    )







    try:



        # Only use saved captions when fresh=False.
        if not fresh:



            cached = get_cached_result(cache_key)







            if cached is not None:



                return add_personalization({





                    **cached,





                    "cached": True,





                    "model": APIYI_MODEL,





                }, user_id, theme, custom_theme)







        previous_captions = get_caption_history(



            cache_key



        )







        previous_normalized = {



            normalize_caption(caption)



            for caption in previous_captions



        }







        last_error = None







        attempts = (



            MAX_GENERATION_ATTEMPTS



            if fresh



            else 1



        )







        for attempt in range(attempts):



            # Each provider call consumes development budget.
            reserve_budget()







            try:



                result_data = request_apiyi(



                    image_bytes,



                    theme,



                    custom_theme,



                    previous_captions,



                    fresh,



                )







                new_normalized = {



                    normalize_caption(caption)



                    for caption in result_data["captions"]



                }







                repeated = (



                    new_normalized



                    & previous_normalized



                )







                if fresh and repeated:



                    last_error = (



                        "APIYI repeated previously "



                        "generated captions."



                    )







                    print(



                        f"Fresh attempt {attempt + 1}: "



                        f"{len(repeated)} repeated captions.",



                        flush=True,



                    )







                    continue







                # Save latest captions and add to history.
                save_cached_result(



                    cache_key,



                    result_data,



                )







                return add_personalization({









                    **result_data,









                    "cached": False,









                    "model": APIYI_MODEL,









                }, user_id, theme, custom_theme)







            except (



                ValueError,



                KeyError,



                TypeError,



            ) as error:



                last_error = str(error)







                print(



                    "AI response error:",



                    last_error,



                    flush=True,



                )







                continue







        raise HTTPException(



            status_code=502,



            detail=(



                "Could not generate five completely new "



                "memes this time. Please try again. "



                f"{last_error or ''}"



            ).strip(),



        )







    except HTTPException:



        raise







    except sqlite3.Error as error:



        print(



            "Database error:",



            str(error),



            flush=True,



        )







        raise HTTPException(



            status_code=500,



            detail=(



                "Caption database error. "



                "Check the backend terminal."



            ),



        )
