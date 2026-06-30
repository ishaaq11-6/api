from flask import Flask, request, Response
import requests
import json
import math
from datetime import datetime, timedelta, timezone
from threading import Lock

app = Flask(__name__)

SAMBA_API_KEY = "e4502644-72e1-41bb-96df-e13aa741a6f9"
SAMBA_URL = "https://api.sambanova.ai/v1/chat/completions"

LOCAL_API_KEY = "Ishaaq1"
OWNER_KEY = "7860"
OWNER_LINK = "https://t.me/KINGxISHAAQ"

AVAILABLE_MODELS = {
    "minimax": "MiniMax-M2.7",
    "deepseek": "DeepSeek-V3.1",
    "llama": "Meta-Llama-3.3-70B-Instruct",
    "gpt-oss": "gpt-oss-120b"
}

# Vercel-safe in-memory storage:
# This prevents internal server errors caused by filesystem writes.
# Note: data is not durable across cold starts / redeploys on serverless hosting.
TEMP_KEYS = {}
DAY_STATS = {}
lock = Lock()


def json_response(data, status=200):
    return Response(
        json.dumps(data, indent=4, ensure_ascii=False),
        status=status,
        mimetype="application/json"
    )


def now_utc():
    return datetime.now(timezone.utc)


def today_key():
    return now_utc().date().isoformat()


def format_dt(dt_obj):
    return dt_obj.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def ensure_day_stats():
    day = today_key()
    with lock:
        if day not in DAY_STATS:
            DAY_STATS[day] = {
                "total_requests": 0,
                "successful_requests": 0,
                "ask_requests": 0,
                "models_requests": 0,
                "key_generate_requests": 0,
                "today_users": [],
                "usage_by_user": {}
            }
        return DAY_STATS[day]


def update_day_stats(endpoint_name, key=None, valid_user=False, successful=False):
    day = today_key()
    with lock:
        stats = ensure_day_stats()

        stats["total_requests"] = int(stats.get("total_requests", 0)) + 1

        if endpoint_name == "ask":
            stats["ask_requests"] = int(stats.get("ask_requests", 0)) + 1
        elif endpoint_name == "models":
            stats["models_requests"] = int(stats.get("models_requests", 0)) + 1
        elif endpoint_name == "keyGenerate":
            stats["key_generate_requests"] = int(stats.get("key_generate_requests", 0)) + 1

        if successful:
            stats["successful_requests"] = int(stats.get("successful_requests", 0)) + 1

        if valid_user and key:
            users = stats.get("today_users", [])
            if key not in users:
                users.append(key)
            stats["today_users"] = users

            usage_map = stats.get("usage_by_user", {})
            if key not in usage_map:
                usage_map[key] = {"requests": 0, "ask": 0, "models": 0}
            usage_map[key]["requests"] = int(usage_map[key].get("requests", 0)) + 1
            if endpoint_name in ("ask", "models"):
                usage_map[key][endpoint_name] = int(usage_map[key].get(endpoint_name, 0)) + 1
            stats["usage_by_user"] = usage_map

        DAY_STATS[day] = stats


def create_or_update_temp_key(new_key, days):
    created_at = now_utc()
    expires_at = created_at + timedelta(days=days)
    with lock:
        TEMP_KEYS[new_key] = {
            "created_at": created_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "valid_days": days
        }
    return created_at, expires_at


def get_temp_key_data(key):
    with lock:
        return TEMP_KEYS.get(key)


def delete_temp_key(key):
    with lock:
        if key in TEMP_KEYS:
            del TEMP_KEYS[key]


def check_key_status(key):
    if key == LOCAL_API_KEY:
        return {"type": "permanent", "valid": True, "expired": False, "days_left": None}

    key_data = get_temp_key_data(key)
    if not key_data:
        return {"type": "temporary", "valid": False, "expired": False, "days_left": None}

    try:
        expires_at = datetime.fromisoformat(key_data["expires_at"])
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        else:
            expires_at = expires_at.astimezone(timezone.utc)
    except Exception:
        return {"type": "temporary", "valid": False, "expired": False, "days_left": None}

    current_time = now_utc()
    remaining_seconds = (expires_at - current_time).total_seconds()

    if remaining_seconds <= 0:
        delete_temp_key(key)
        return {"type": "temporary", "valid": False, "expired": True, "days_left": 0}

    days_left = math.ceil(remaining_seconds / 86400)
    return {"type": "temporary", "valid": True, "expired": False, "days_left": days_left}


def expired_response():
    return json_response({
        "success": False,
        "error": "Key expired.",
        "message": "Contact owner to buy new key.",
        "owner": OWNER_LINK
    }, 401)


def invalid_key_response():
    return json_response({
        "success": False,
        "error": "Invalid API key.",
        "owner": OWNER_LINK
    }, 401)


@app.route("/keyGenerate", methods=["GET"])
def key_generate():
    update_day_stats("keyGenerate", key=None, valid_user=False, successful=False)

    owner_key = request.args.get("OwnerKey", "")
    new_key = request.args.get("NewKey", "")
    day = request.args.get("day", "")

    if owner_key != OWNER_KEY:
        return json_response({
            "success": False,
            "error": "Invalid owner key.",
            "owner": OWNER_LINK
        }, 401)

    if not new_key:
        return json_response({
            "success": False,
            "error": "NewKey is required.",
            "owner": OWNER_LINK
        }, 400)

    try:
        day = int(day)
        if day <= 0:
            raise ValueError
    except Exception:
        return json_response({
            "success": False,
            "error": "day must be a positive integer.",
            "owner": OWNER_LINK
        }, 400)

    created_at, expires_at = create_or_update_temp_key(new_key, day)

    return json_response({
        "success": True,
        "message": "Temporary key generated successfully.",
        "key": new_key,
        "valid_days": day,
        "created_at": format_dt(created_at),
        "expires_at": format_dt(expires_at),
        "owner": OWNER_LINK
    })


@app.route("/ask", methods=["GET"])
def ask():
    message = request.args.get("message", "")
    key = request.args.get("key", "")
    model_choice = request.args.get("model", "llama")

    if not key:
        update_day_stats("ask", key=None, valid_user=False, successful=False)
        return json_response({
            "success": False,
            "error": "Key required.",
            "owner": OWNER_LINK
        }, 401)

    key_status = check_key_status(key)

    if not key_status["valid"]:
        update_day_stats("ask", key=key, valid_user=False, successful=False)
        if key_status["expired"]:
            return expired_response()
        return invalid_key_response()

    if not message:
        update_day_stats("ask", key=key, valid_user=True, successful=False)
        return json_response({
            "success": False,
            "error": "Message required.",
            "owner": OWNER_LINK
        }, 400)

    model_name = AVAILABLE_MODELS.get(model_choice, AVAILABLE_MODELS["llama"])

    headers = {
        "Authorization": f"Bearer {SAMBA_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": "You are a helpful AI assistant."},
            {"role": "user", "content": message}
        ],
        "temperature": 0.7,
        "max_tokens": 500,
        "top_p": 0.95
    }

    try:
        response = requests.post(SAMBA_URL, headers=headers, json=payload, timeout=30)

        if response.status_code == 200:
            data = response.json()
            reply = data["choices"][0]["message"]["content"]

            result = {
                "success": True,
                "message": message,
                "reply": reply,
                "model": model_name,
                "owner": OWNER_LINK
            }

            if key_status["type"] == "temporary":
                result["days_left_to_expire_key"] = key_status["days_left"]

            update_day_stats("ask", key=key, valid_user=True, successful=True)
            return json_response(result)

        update_day_stats("ask", key=key, valid_user=True, successful=False)
        return json_response({
            "success": False,
            "error": f"API Error: {response.status_code}",
            "details": response.text,
            "owner": OWNER_LINK
        }, response.status_code)

    except Exception as e:
        update_day_stats("ask", key=key, valid_user=True, successful=False)
        return json_response({
            "success": False,
            "error": str(e),
            "owner": OWNER_LINK
        }, 500)


@app.route("/models", methods=["GET"])
def show_models():
    key = request.args.get("key", "")

    if not key:
        update_day_stats("models", key=None, valid_user=False, successful=False)
        return json_response({
            "success": False,
            "error": "Key required.",
            "owner": OWNER_LINK
        }, 401)

    key_status = check_key_status(key)

    if not key_status["valid"]:
        update_day_stats("models", key=key, valid_user=False, successful=False)
        if key_status["expired"]:
            return expired_response()
        return invalid_key_response()

    result = {
        "success": True,
        "models": AVAILABLE_MODELS,
        "usage_examples": {
            "llama": "/ask?message=hello&key=YOUR_KEY&model=llama",
            "deepseek": "/ask?message=hi&key=YOUR_KEY&model=deepseek",
            "minimax": "/ask?message=namaste&key=YOUR_KEY&model=minimax",
            "gpt-oss": "/ask?message=how are you&key=YOUR_KEY&model=gpt-oss"
        },
        "owner": OWNER_LINK
    }

    if key_status["type"] == "temporary":
        result["days_left_to_expire_key"] = key_status["days_left"]

    update_day_stats("models", key=key, valid_user=True, successful=True)
    return json_response(result)


@app.route("/Status", methods=["GET"])
@app.route("/status", methods=["GET"])
def status():
    owner_key = request.args.get("ownerKey", "")
    if owner_key != OWNER_KEY:
        return json_response({
            "success": False,
            "error": "Invalid owner key.",
            "owner": OWNER_LINK
        }, 401)

    day_stats = ensure_day_stats()
    return json_response({
        "success": True,
        "date": today_key(),
        "today_usage": {
            "total_requests": day_stats.get("total_requests", 0),
            "successful_requests": day_stats.get("successful_requests", 0),
            "ask_requests": day_stats.get("ask_requests", 0),
            "models_requests": day_stats.get("models_requests", 0),
            "key_generate_requests": day_stats.get("key_generate_requests", 0)
        },
        "today_users_count": len(day_stats.get("today_users", [])),
        "today_users": day_stats.get("today_users", []),
        "usage_by_user": day_stats.get("usage_by_user", {}),
        "owner": OWNER_LINK
    })


@app.route("/", methods=["GET"])
def home():
    return json_response({
        "success": True,
        "api": "Ishaaq AI API",
        "version": "1.0",
        "endpoints": {
            "/ask": {
                "method": "GET",
                "usage": "Use this endpoint to ask the AI. Example: /ask?message=hello&key=YOUR_API_KEY&model=llama",
                "description": "Send a message to the AI and get a response."
            },
            "/models": {
                "method": "GET",
                "usage": "Use this endpoint to view the available models. Example: /models?key=YOUR_API_KEY",
                "description": "Show available AI models."
            }
        },
        "available_models": ["llama", "deepseek", "minimax", "gpt-oss"],
        "message": "Welcome to Ishaaq AI API.",
        "owner": OWNER_LINK
    })
