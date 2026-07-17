import cv2

VIDEO_PATH = "../../data/simulation/camera/Video.mov"

cap = cv2.VideoCapture(VIDEO_PATH)

while True:
    ret, frame = cap.read()

    if not ret:
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 100, 200)

    cv2.imshow("Original", frame)
    cv2.imshow("Edges (Perception)", edges)

    if cv2.waitKey(30) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
