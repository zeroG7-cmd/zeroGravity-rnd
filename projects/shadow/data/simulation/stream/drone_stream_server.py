from flask import Flask, Response
import cv2

app = Flask(__name__)

VIDEO_PATH = "/home/zero/shadow-drone-rnd/data/simulation/camera/Video.mov"

cap = cv2.VideoCapture(VIDEO_PATH)

def generate_frames():
    while True:
        success, frame = cap.read()

        if not success:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue

        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video')
def video():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    print("Stream running at http://127.0.0.1:5000/video")
    app.run(host='0.0.0.0', port=5000, debug=False)
