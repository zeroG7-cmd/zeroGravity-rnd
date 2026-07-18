from __future__ import annotations
from pathlib import Path
import cv2

VIDEO_PATH = (
    Path(__file__).resolve().parents[3]
    / "data" / "simulation" / "camera" / "Video.mov"
)

def main() -> int:
    if not VIDEO_PATH.exists():
        print(f"Video not found: {VIDEO_PATH}")
        return 1

    capture = cv2.VideoCapture(str(VIDEO_PATH))
    try:
        while True:
            success, frame = capture.read()
            if not success:
                break
            cv2.imshow("Shadow Pipeline", frame)

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 100, 200)
            cv2.imshow("Edges (Perception)", edges)
            if cv2.waitKey(30) & 0xFF == ord("q"):
                break
    finally:
        capture.release()
        cv2.destroyAllWindows()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
