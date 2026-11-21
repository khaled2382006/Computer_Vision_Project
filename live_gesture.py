import os, math, time, urllib.request
import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

# ===== الموديل =====
MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hand_landmarker.task")
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"

if not os.path.exists(MODEL_PATH):
    print("بحمّل الموديل...")
    urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)

with open(MODEL_PATH, "rb") as f:
    model_bytes = f.read()

options = vision.HandLandmarkerOptions(
    base_options=mp_python.BaseOptions(model_asset_buffer=model_bytes),
    running_mode=vision.RunningMode.VIDEO,
    num_hands=1,
    min_hand_detection_confidence=0.6,
    min_tracking_confidence=0.6,
)
detector = vision.HandLandmarker.create_from_options(options)

HAND_CONNECTIONS = [
    (0,1),(1,2),(2,3),(3,4),
    (0,5),(5,6),(6,7),(7,8),
    (5,9),(9,10),(10,11),(11,12),
    (9,13),(13,14),(14,15),(15,16),
    (13,17),(17,18),(18,19),(19,20),(0,17)
]

# ===== الدوال =====
def calculate_distance(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)

def count_fingers(lm):
    wrist = lm[0]
    tips = [8, 12, 16, 20]
    pips = [6, 10, 14, 18]
    return [
        1 if calculate_distance(lm[t], wrist) >
             calculate_distance(lm[p], wrist) * 1.1 else 0
        for t, p in zip(tips, pips)
    ]

def detect_thumb(lm):
    palm_width = calculate_distance(lm[5], lm[17])
    away_from_pinky = (calculate_distance(lm[4], lm[17]) >
                       calculate_distance(lm[3], lm[17]) * 1.05)
    away_from_index = calculate_distance(lm[4], lm[5]) > palm_width * 0.7
    return away_from_pinky and away_from_index

def recognize_gesture_v2(lm):
    fingers = count_fingers(lm)
    thumb_open = detect_thumb(lm)
    total = sum(fingers)
    palm_width = calculate_distance(lm[5], lm[17])
    thumb_tip, wrist = lm[4], lm[0]

    if (calculate_distance(lm[4], lm[8]) < palm_width * 0.25
            and fingers[1] == 1 and fingers[2] == 1 and fingers[3] == 1):
        return "OK SIGN"

    if thumb_open and total == 0:
        if thumb_tip.y < wrist.y - palm_width * 0.5:
            return "THUMBS UP"
        if thumb_tip.y > wrist.y + palm_width * 0.5:
            return "THUMBS DOWN"

    if total == 4: return "OPEN PALM"
    if total == 0: return "CLOSED FIST"
    if total == 1: return "ONE FINGER"
    if total == 2: return "TWO FINGERS"
    if total == 3: return "THREE FINGERS"
    return "UNKNOWN"

# ===== الكاميرا =====
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
print("opened:", cap.isOpened())
start = time.time()

while cap.isOpened():
    ok, frame = cap.read()
    if not ok:
        print("can't read frame")
        break

    frame = cv2.flip(frame, 1)  # مراية عشان الحركة تبقى طبيعية
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    timestamp = int((time.time() - start) * 1000)
    result = detector.detect_for_video(mp_image, timestamp)

    gesture = "NO HAND"
    if result.hand_landmarks:
        hand = result.hand_landmarks[0]
        gesture = recognize_gesture_v2(hand)

        h, w, _ = frame.shape
        points = [(int(p.x * w), int(p.y * h)) for p in hand]
        for s, e in HAND_CONNECTIONS:
            cv2.line(frame, points[s], points[e], (0, 255, 0), 2)
        for pt in points:
            cv2.circle(frame, pt, 4, (255, 0, 0), -1)

    cv2.putText(frame, gesture, (20, 50), cv2.FONT_HERSHEY_SIMPLEX,
                1.3, (0, 0, 255), 3)
    cv2.imshow("Live Gesture", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()