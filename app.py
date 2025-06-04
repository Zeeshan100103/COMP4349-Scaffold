#!/usr/bin/env python3
"""
COMP5349 Assignment: Image Captioning App using Gemini API and AWS Services

IMPORTANT:
Before running this application, ensure that you update the following configurations:
1. Replace the GEMINI API key (`GOOGLE_API_KEY`) with your own key from Google AI Studio.
2. Replace the AWS S3 bucket name (`S3_BUCKET`) with your own S3 bucket.
3. Update the RDS MySQL database credentials (`DB_HOST`, `DB_USER`, `DB_PASSWORD`).
4. Ensure all necessary dependencies are installed by running the provided setup script.

Failure to update these values will result in authentication errors or failure to access cloud services.
"""

import base64
from io import BytesIO

import boto3
import google.generativeai as genai
import mysql.connector
from flask import Flask, request, render_template
from werkzeug.utils import secure_filename

# ── CONFIGURATION ───────────────────────────────────────────────────────────────

# Gemini API
GOOGLE_API_KEY = "AIzaSyD7_nrNfq4noFX2CWO-Bg5ZtTtedhohwNw"
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel(model_name="gemini-2.5-flash-preview-04-17")

# AWS / S3
S3_BUCKET = "image-app-bucket-096340956834506"
S3_REGION = "us-east-1"

# RDS / MySQL
DB_HOST     = "imageapp-db.ckaduid0n0l9.us-east-1.rds.amazonaws.com"
DB_NAME     = "imageappdb"
DB_USER     = "admin"
DB_PASSWORD = "alphabetagamma"

# File uploads
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

# ── HELPERS ────────────────────────────────────────────────────────────────────

def get_s3_client():
    return boto3.client("s3", region_name=S3_REGION)

def get_db_connection():
    try:
        return mysql.connector.connect(
            host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
        )
    except mysql.connector.Error as e:
        print("DB connection error:", e)
        return None

def allowed_file(fname):
    return "." in fname and fname.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_image_caption(image_bytes):
    try:
        encoded = base64.b64encode(image_bytes).decode("utf-8")
        resp = model.generate_content(
            [
                {"mime_type": "image/jpeg", "data": encoded},
                "Caption this image.",
            ]
        )
        return resp.text or "No caption generated."
    except Exception as e:
        return f"Error generating caption: {e}"

# ── FLASK APP ─────────────────────────────────────────────────────────────────

app = Flask(__name__)

@app.route("/health")
def health():
    return "OK", 200

@app.route("/")
def upload_form():
    return render_template("index.html")

@app.route("/upload", methods=["GET", "POST"])
def upload_image():
    if request.method == "POST":
        file = request.files.get("file")
        if not file or file.filename == "" or not allowed_file(file.filename):
            return render_template("upload.html", error="Please select a valid image file.")
        filename = secure_filename(file.filename)
        data = file.read()
        upload_key = f"uploads/{filename}"

        # 1. Upload to S3
        try:
            get_s3_client().upload_fileobj(BytesIO(data), S3_BUCKET, upload_key)
        except Exception as e:
            return render_template("upload.html", error=f"S3 error: {e}")

        # 2. Generate caption
        caption = generate_image_caption(data)

        # 3. Save to RDS
        conn = get_db_connection()
        if not conn:
            return render_template("upload.html", error="Database connection failed.")
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO captions (image_key, caption) VALUES (%s, %s)",
            (filename, caption)
        )
        conn.commit()
        conn.close()

        # 4. Prepare for display
        img_b64 = base64.b64encode(data).decode("utf-8")
        file_url = f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com/{filename}"
        return render_template("upload.html",
                               image_data=img_b64,
                               file_url=file_url,
                               caption=caption)

    return render_template("upload.html")

@app.route("/gallery")
def gallery():
    """
    Retrieves thumbnails and their captions from the database,
    generates pre-signed URLs for secure access, and renders the gallery page.
    """
    try:
        connection = get_db_connection()
        if connection is None:
            return render_template("gallery.html", error="Database Error: Unable to connect to the database.")
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT image_key, caption FROM captions ORDER BY uploaded_at DESC")
        results = cursor.fetchall()
        connection.close()

        images_with_captions = []
        s3 = get_s3_client()
        for row in results:
            # The thumbnail lives under "thumbnails/<filename>"
            thumb_key = f"thumbnails/{row['image_key']}"
            url = s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": S3_BUCKET, "Key": thumb_key},
                ExpiresIn=3600,
            )
            images_with_captions.append({
                "url": url,
                "caption": row["caption"],
            })

        return render_template("gallery.html", images=images_with_captions)

    except Exception as e:
        return render_template("gallery.html", error=f"Database Error: {str(e)}")


if __name__ == "__main__":
    # Bind to port 80 so ALB health checks (and user traffic) succeed
    app.run(host="0.0.0.0", port=80)
