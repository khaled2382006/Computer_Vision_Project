import cv2

cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
print("opened:", cap.isOpened())

while cap.isOpened():
    ok, frame = cap.read()
    if not ok:
        print("can't read frame")
        break
    cv2.imshow("Camera", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()