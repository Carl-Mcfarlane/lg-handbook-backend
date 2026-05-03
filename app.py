"""
LG Handbook Backend API
Flask + MongoDB + JWT Authentication
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_bcrypt import Bcrypt
from pymongo import MongoClient
from dotenv import load_dotenv
import jwt
import os
import datetime

# =====================================================
# App Setup
# =====================================================

load_dotenv()

app = Flask(__name__)
CORS(app)
bcrypt = Bcrypt(app)

MAPS_API_KEY = os.getenv("MAPS_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")
SECRET_KEY = os.getenv("SECRET_KEY")
INVITE_CODE = os.getenv("INVITE_CODE")


# =====================================================
# Database Helper
# =====================================================

def get_db():
    client = MongoClient(MONGO_URI)
    return client["Lifeguard_Techniques"]


# =====================================================
# Auth Helpers
# =====================================================

def decode_token(req):
    token = req.headers.get("Authorization", "").replace("Bearer ", "")
    if not token:
        return None

    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def require_admin(payload):
    return payload and payload.get("role") == "admin"


def current_week():
    return datetime.datetime.utcnow().strftime("%Y-W%W")


# =====================================================
# Authentication Routes
# =====================================================

@app.route("/api/register", methods=["POST"])
def register():
    data = request.json
    db = get_db()

    if data.get("invite_code") != INVITE_CODE:
        return jsonify({"error": "Invalid invite code"}), 403

    if db["Users"].find_one({"email": data["email"]}):
        return jsonify({"error": "Email already registered"}), 400

    hashed = bcrypt.generate_password_hash(
        data["password"]
    ).decode("utf-8")

    db["Users"].insert_one({
        "name": data["name"],
        "email": data["email"],
        "password": hashed,
        "role": "lifeguard"
    })

    return jsonify({"message": "Account created successfully"})


@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    db = get_db()

    user = db["Users"].find_one({"email": data["email"]})

    if not user or not bcrypt.check_password_hash(
        user["password"], data["password"]
    ):
        return jsonify({"error": "Invalid email or password"}), 401

    token = jwt.encode(
        {
            "user_id": str(user["_id"]),
            "name": user["name"],
            "role": user["role"],
            "exp": datetime.datetime.utcnow()
                   + datetime.timedelta(days=7),
        },
        SECRET_KEY,
        algorithm="HS256",
    )

    return jsonify({
        "token": token,
        "name": user["name"],
        "role": user["role"],
    })


@app.route("/api/me")
def me():
    payload = decode_token(request)
    if not payload:
        return jsonify({"error": "Unauthorized"}), 401

    return jsonify(payload)


# =====================================================
# Attendance
# =====================================================

@app.route("/api/attendance", methods=["POST"])
def mark_attendance():
    payload = decode_token(request)
    if not payload:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    db = get_db()
    week = current_week()

    existing = db["Attendance"].find_one({
        "user_id": payload["user_id"],
        "pool": data["pool"],
        "day": data["day"],
        "week": week
    })

    if existing:
        db["Attendance"].delete_one({"_id": existing["_id"]})
        return jsonify({"attending": False})

    db["Attendance"].insert_one({
        "user_id": payload["user_id"],
        "user_name": payload["name"],
        "pool": data["pool"],
        "day": data["day"],
        "time": data["time"],
        "week": week,
    })

    return jsonify({"attending": True})


@app.route("/api/attendance/me")
def my_attendance():
    payload = decode_token(request)
    if not payload:
        return jsonify({"error": "Unauthorized"}), 401

    db = get_db()

    results = list(db["Attendance"].find(
        {"user_id": payload["user_id"], "week": current_week()},
        {"_id": 0},
    ))

    return jsonify(results)


@app.route("/api/attendance/history")
def attendance_history():
    payload = decode_token(request)
    if not payload:
        return jsonify({"error": "Unauthorized"}), 401

    db = get_db()

    results = list(
        db["Attendance"]
        .find({"user_id": payload["user_id"]}, {"_id": 0})
        .sort("week", -1)
    )

    return jsonify(results)


# =====================================================
# Admin Routes
# =====================================================

@app.route("/api/attendance/all")
def all_attendance():
    payload = decode_token(request)
    if not require_admin(payload):
        return jsonify({"error": "Forbidden"}), 403

    db = get_db()

    results = list(db["Attendance"].find(
        {"week": current_week()},
        {"_id": 0},
    ))

    return jsonify(results)


@app.route("/api/attendance/user/<user_name>")
def user_attendance(user_name):
    payload = decode_token(request)
    if not require_admin(payload):
        return jsonify({"error": "Forbidden"}), 403

    db = get_db()

    results = list(
        db["Attendance"]
        .find({"user_name": user_name}, {"_id": 0})
        .sort("week", -1)
    )

    return jsonify(results)


@app.route("/api/users")
def get_users():
    payload = decode_token(request)
    if not require_admin(payload):
        return jsonify({"error": "Forbidden"}), 403

    db = get_db()

    results = list(db["Users"].find(
        {},
        {"_id": 0, "password": 0},
    ))

    return jsonify(results)


# =====================================================
# Core Data Routes
# =====================================================

@app.route("/api/techniques")
def techniques():
    db = get_db()
    results = list(
        db["Lifeguard_Techniques"]
        .find({}, {"_id": 0}, sort=[("name", 1)])
    )
    return jsonify(results)


@app.route("/api/equipment")
def equipment():
    db = get_db()
    results = list(
        db["LG_Equipment"]
        .find({}, {"_id": 0}, sort=[("name", 1)])
    )
    return jsonify(results)


@app.route("/api/schedule")
def schedule():
    db = get_db()
    results = list(
        db["LG_Trainings"]
        .find({}, {"_id": 0}, sort=[("pool", 1)])
    )
    return jsonify(results)


@app.route("/api/supervisors")
def supervisors():
    db = get_db()
    results = list(
        db["Supervisors"]
        .find({}, {"_id": 0}, sort=[("pool", 1)])
    )
    return jsonify(results)


@app.route("/api/documents")
def documents():
    db = get_db()
    results = list(
        db["Documents"]
        .find({}, {"_id": 0}, sort=[("type", 1)])
    )
    return jsonify(results)


# =====================================================
# Maps
# =====================================================

@app.route("/api/mapurl")
def map_url():
    lat = request.args.get("lat")
    lng = request.args.get("lng")

    url = (
        "https://maps.googleapis.com/maps/api/staticmap"
        f"?center={lat},{lng}"
        "&zoom=15"
        "&size=400x160"
        f"&markers=color:red%7C{lat},{lng}"
        f"&key={MAPS_API_KEY}"
    )

    return jsonify({"url": url})


# =====================================================
# Announcements
# =====================================================

@app.route("/api/announcements")
def announcements():
    db = get_db()

    results = list(
        db["Announcements"]
        .find({}, {"_id": 0})
        .sort("date", -1)
    )

    return jsonify(results)


@app.route("/api/announcements", methods=["POST"])
def post_announcement():
    payload = decode_token(request)
    if not require_admin(payload):
        return jsonify({"error": "Forbidden"}), 403

    data = request.json
    db = get_db()

    db["Announcements"].insert_one({
        "title": data.get("title"),
        "message": data.get("message"),
        "author": payload["name"],
        "date": datetime.datetime.utcnow().strftime("%Y-%m-%d"),
        "pinned": data.get("pinned", False),
    })

    return jsonify({"message": "Announcement posted"})


# =====================================================
# Run Server
# =====================================================

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")