from flask import Flask, jsonify, request
from flask_cors import CORS
from pymongo import MongoClient
from dotenv import load_dotenv
from flask_bcrypt import Bcrypt
import jwt
import os
import datetime

load_dotenv()

app = Flask(__name__)
CORS(app) # Allow frontend to talk to backend
bcrypt = Bcrypt(app)

# Env config
MAPS_API_KEY = os.getenv("MAPS_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")
SECRET_KEY = os.getenv("SECRET_KEY")
INVITE_CODE = os.getenv("INVITE_CODE")

# Establish DB connection once
client = MongoClient(MONGO_URI)
db = client["Lifeguard_Techniques"]

def decode_token(req):
    """ Extract and verify JWT from headers """
    token = req.headers.get("Authorization", "").replace("Bearer ", "")
    if not token:
        return None
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except:
        return None

def get_iso_week():
    """ Consistent week string (Monday-Sunday) to prevent syncing issues """
    now = datetime.datetime.now(datetime.timezone.utc)
    iso_year, iso_week, _ = now.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"

# --- User Management ---

@app.route("/api/register", methods=["POST"])
def register():
    data = request.json
    if data.get("invite_code") != INVITE_CODE:
        return jsonify({"error": "Invalid invite code"}), 403

    if db["Users"].find_one({"email": data["email"]}):
        return jsonify({"error": "User already exists"}), 400

    hashed_pw = bcrypt.generate_password_hash(data["password"]).decode("utf-8")
    db["Users"].insert_one({
        "name": data["name"],
        "email": data["email"],
        "password": hashed_pw,
        "role": "lifeguard"
    })
    return jsonify({"message": "User registered"})

@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    user = db["Users"].find_one({"email": data["email"]})
    
    if not user or not bcrypt.check_password_hash(user["password"], data["password"]):
        return jsonify({"error": "Invalid credentials"}), 401

    token = jwt.encode({
        "user_id": str(user["_id"]),
        "name": user["name"],
        "role": user["role"],
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7)
    }, SECRET_KEY, algorithm="HS256")

    return jsonify({"token": token, "name": user["name"], "role": user["role"]})

@app.route("/api/forgot-password", methods=["POST"])
def forgot_pw():
    # Placeholder for actual email service integration
    return jsonify({"message": "If this email is on file, we've sent a reset link."})

# --- Attendance Engine ---

@app.route("/api/attendance", methods=["POST"])
def toggle_attendance():
    payload = decode_token(request)
    if not payload: return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    week_id = get_iso_week()

    # Look for an existing check-in to see if we should delete (un-attend) or create
    query = {
        "user_id": payload["user_id"],
        "pool": data["pool"],
        "day": data["day"],
        "week": week_id
    }

    exists = db["Attendance"].find_one(query)
    if exists:
        db["Attendance"].delete_one({"_id": exists["_id"]})
        return jsonify({"attending": False})
    else:
        db["Attendance"].insert_one({
            **query,
            "user_name": payload["name"],
            "time": data["time"]
        })
        return jsonify({"attending": True})

@app.route("/api/attendance/me")
def get_my_week():
    payload = decode_token(request)
    if not payload: return jsonify({"error": "Unauthorized"}), 401
    
    week_id = get_iso_week()
    res = list(db["Attendance"].find({"user_id": payload["user_id"], "week": week_id}, {"_id": 0}))
    return jsonify(res)

@app.route("/api/attendance/history")
def get_full_history():
    payload = decode_token(request)
    if not payload: return jsonify({"error": "Unauthorized"}), 401
    
    res = list(db["Attendance"].find({"user_id": payload["user_id"]}, {"_id": 0}).sort("week", -1))
    return jsonify(res)

# --- Admin Routes ---

@app.route("/api/users")
def list_users():
    payload = decode_token(request)
    if not payload or payload.get("role") != "admin": return jsonify({"error": "Forbidden"}), 403
    return jsonify(list(db["Users"].find({}, {"_id": 0, "password": 0})))

@app.route("/api/attendance/all")
def admin_get_all():
    payload = decode_token(request)
    if not payload or payload.get("role") != "admin": return jsonify({"error": "Forbidden"}), 403
    
    week_id = get_iso_week()
    return jsonify(list(db["Attendance"].find({"week": week_id}, {"_id": 0})))

@app.route("/api/announcements", methods=["POST"])
def post_update():
    payload = decode_token(request)
    if not payload or payload.get("role") != "admin": return jsonify({"error": "Forbidden"}), 403
    
    db["Announcements"].insert_one({
        **request.json,
        "author": payload["name"],
        "date": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    })
    return jsonify({"message": "Posted"})

# --- Static Data Routes ---

@app.route("/api/techniques")
def get_tech():
    return jsonify(list(db["Lifeguard_Techniques"].find({}, {"_id": 0}).sort("name", 1)))

@app.route("/api/equipment")
def get_equip():
    return jsonify(list(db["LG_Equipment"].find({}, {"_id": 0}).sort("name", 1)))

@app.route("/api/schedule")
def get_schedule():
    return jsonify(list(db["LG_Trainings"].find({}, {"_id": 0}).sort("pool", 1)))

@app.route("/api/supervisors")
def get_supervisors():
    return jsonify(list(db["Supervisors"].find({}, {"_id": 0})))

@app.route("/api/documents")
def get_docs():
    return jsonify(list(db["Documents"].find({}, {"_id": 0})))

@app.route("/api/announcements")
def get_announcements():
    return jsonify(list(db["Announcements"].find({}, {"_id": 0}).sort("date", -1)))

if __name__ == "__main__":
    # Standard dev port
    app.run(debug=True, host="0.0.0.0", port=5000)