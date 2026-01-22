from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
import requests
import os
from pymongo import MongoClient
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")

HEADERS = {
    "Authorization": f"Bearer {WHATSAPP_TOKEN}"
}

# MongoDB setup
client = MongoClient(os.getenv("MONGO_URI"))
db = client["whatsapp_db"]
collection = db["payments"]

# -------------------------------
# Webhook verification (GET)
# -------------------------------
@app.get("/webhook")
def webhook_verify(request: Request):
    params = request.query_params

    hub_verify_token = params.get("hub.verify_token")
    hub_challenge = params.get("hub.challenge")

    if hub_verify_token == VERIFY_TOKEN and hub_challenge:
        return PlainTextResponse(content=hub_challenge)

    return PlainTextResponse(content="Verification failed", status_code=403)

# -------------------------------
# Receive messages (POST)
# -------------------------------
@app.post("/webhook")
async def receive_message(request: Request):
    payload = await request.json()

    try:
        entry = payload["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]

        if "messages" not in value:
            return {"status": "ignored"}

        message = value["messages"][0]

        sender = message["from"]  # phone number
        msg_type = message["type"]

        text_message = None
        image_path = None

        # -------------------------------
        # Extract text message
        # -------------------------------
        if msg_type == "text":
            text_message = message["text"]["body"]

        # -------------------------------
        # Extract image
        # -------------------------------
        if msg_type == "image":
            media_id = message["image"]["id"]

            # Step 1: Get media URL
            media_res = requests.get(
                f"https://graph.facebook.com/v18.0/{media_id}",
                headers=HEADERS
            ).json()

            media_url = media_res["url"]

            # Step 2: Download image
            image_bytes = requests.get(media_url, headers=HEADERS).content

            image_path = f"images/{media_id}.jpg"
            os.makedirs("images", exist_ok=True)

            with open(image_path, "wb") as f:
                f.write(image_bytes)

        # -------------------------------
        # Store in MongoDB
        # -------------------------------
        collection.insert_one({
            "sender": sender,
            "text": text_message,
            "image_path": image_path,
            "timestamp": datetime.utcnow()
        })

        return {"status": "stored"}

    except Exception as e:
        print("Error:", e)
        return {"status": "error"}
