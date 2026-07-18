from __future__ import annotations
from pathlib import Path
from flask import Flask, Response, jsonify
import cv2

app = Flask(__name__)
VIDEO_PATH = Path(__file__).resolve().parents[2] / "camera" / "Video.mov"

def generate_frames():
    capture = cv2.VideoCapture(str(VIDEO_PATH))
    try:
        while capture.isOpened():
            success, frame = capture.read()
            if not success:
                capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
            encoded, buffer = cv2.imencode(".jpg", frame)
            if encoded:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n"
                    + buffer.tobytes()
                    + b"\r\n"
                )
    finally:
        capture.release()

@app.get("/")
def status():
    return jsonify(
        {
            "service": "Shadow simulation stream",
            "video": str(VIDEO_PATH),
            "available": VIDEO_PATH.exists(),
        }
    )

@app.get("/video")
def video():
    return Response(
        generate_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )

if __name__ == "__main__":
    if not VIDEO_PATH.exists():
        print(f"WARNING: video not found: {VIDEO_PATH}")
    app.run(host="0.0.0.0", port=5000, debug=False)
