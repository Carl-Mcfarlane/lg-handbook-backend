from flask import Flask, jsonify, request
from flask_cors import CORS
from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)
CORS(app)

MAPS_API_KEY = os.getenv("MAPS_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")

def get_db():
    client = MongoClient(MONGO_URI)
    return client["Lifeguard_Techniques"]

@app.route("/api/techniques")
def techniques():
    db = get_db()
    results = list(db["Lifeguard_Techniques"].find({}, {"_id": 0}, sort=[("name", 1)]))
    return jsonify(results)

@app.route("/api/equipment")
def equipment():
    db = get_db()
    results = list(db["LG_Equipment"].find({}, {"_id": 0}, sort=[("name", 1)]))
    return jsonify(results)

@app.route("/api/schedule")
def schedule():
    db = get_db()
    results = list(db["LG_Trainings"].find({}, {"_id": 0}, sort=[("pool", 1)]))
    return jsonify(results)

@app.route("/api/supervisors")
def supervisors():
    db = get_db()
    results = list(db["Supervisors"].find({}, {"_id": 0}, sort=[("pool", 1)]))
    return jsonify(results)

@app.route("/api/mapurl")
def map_url():
    lat = request.args.get("lat")
    lng = request.args.get("lng")
    url = f"https://maps.googleapis.com/maps/api/staticmap?center={lat},{lng}&zoom=15&size=400x160&markers=color:red%7C{lat},{lng}&key={MAPS_API_KEY}"
    return jsonify({"url": url})

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")