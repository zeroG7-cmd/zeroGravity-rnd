import cv2

STREAM_URL = "http://localhost:5000/video"

cap = cv2.VideoCapture(STREAM_URL)

while True:
    ret, frame = cap.read()

    if not ret:
        break

    cv2.imshow("Fake Drone Feed", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
