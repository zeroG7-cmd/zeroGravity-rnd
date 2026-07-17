import cv2

VIDEO_PATH = "../../data/simulation/camera/Video.mov"

cap = cv2.VideoCapture(VIDEO_PATH)

while True:
    ret, frame = cap.read()

    if not ret:
        print("End of video")
        break

    cv2.imshow("Shadow Pipeline", frame)

    if cv2.waitKey(30) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
