import os, math, time, urllib.request
from ctypes import cast, POINTER
import cv2
import mediapipe as mp
import pyautogui
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
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

# ===== التحكم في الصوت =====
speakers = AudioUtilities.GetSpeakers()
try:
    volume = speakers.EndpointVolume          # نسخ pycaw الجديدة
except AttributeError:
    interface = speakers.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume = cast(interface, POINTER(IAudioEndpointVolume))

smooth_vol = volume.GetMasterVolumeLevelScalar()

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
    hand_size = calculate_distance(lm[0], lm[9])   # المعصم لقاعدة الوسطى
    thumb_tip, wrist = lm[4], lm[0]

    # OK sign: الإبهام والسبابة ملتصقين، واتنين من التلاتة التانيين مفرودين
    pinch = calculate_distance(lm[4], lm[8]) / hand_size
    others_up = 0
    for tip, pip in [(12, 10), (16, 14), (20, 18)]:
        if calculate_distance(lm[tip], lm[0]) > calculate_distance(lm[pip], lm[0]):
            others_up += 1
    if pinch < 0.35 and others_up >= 2:
        return "OK SIGN"

    # Thumbs up / down
    if thumb_open and total == 0:
        if thumb_tip.y < wrist.y - palm_width * 0.5:
            return "THUMBS UP"
        if thumb_tip.y > wrist.y + palm_width * 0.5:
            return "THUMBS DOWN"

    # وضع التحكم المستمر في الصوت (إبهام + سبابة)
    if thumb_open and fingers == [1, 0, 0, 0]:
        return "VOLUME MODE"

    if total == 4: return "OPEN PALM"
    if total == 0: return "CLOSED FIST"
    if total == 1: return "ONE FINGER"
    if total == 2: return "TWO FINGERS"
    if total == 3: return "THREE FINGERS"
    return "UNKNOWN"
# ===== الأوامر =====
ACTIONS = {
    "OPEN PALM":     ("playpause",  1.5),
    "THUMBS UP":     ("volumeup",   0.3),
    "THUMBS DOWN":   ("volumedown", 0.3),
    "OK SIGN":       ("volumemute", 1.5),
    "TWO FINGERS":   ("nexttrack",  1.5),
    "THREE FINGERS": ("prevtrack",  1.5),
}

STABLE_FRAMES = 5
history = []
last_fire = {}

# ===== القفل =====
locked = True
HOLD_SECONDS = 1.5
one_start = None
lock_done = False

# ===== رسالة التأكيد =====
last_action = ""
last_action_time = 0

# ===== الكاميرا =====
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
print("opened:", cap.isOpened())
start = time.time()

while cap.isOpened():
    ok, frame = cap.read()
    if not ok:
        print("can't read frame")
        break

    frame = cv2.flip(frame, 1)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    timestamp = int((time.time() - start) * 1000)
    result = detector.detect_for_video(mp_image, timestamp)

    gesture = "NO HAND"
    hand = None
    if result.hand_landmarks:
        hand = result.hand_landmarks[0]
        gesture = recognize_gesture_v2(hand)

        h, w, _ = frame.shape
        points = [(int(p.x * w), int(p.y * h)) for p in hand]
        for s, e in HAND_CONNECTIONS:
            cv2.line(frame, points[s], points[e], (0, 255, 0), 2)
        for pt in points:
            cv2.circle(frame, pt, 4, (255, 0, 0), -1)

    now = time.time()

    # القفل / الفتح بإصبع واحد
    if gesture == "ONE FINGER":
        if one_start is None:
            one_start = now
        elif not lock_done and now - one_start >= HOLD_SECONDS:
            locked = not locked
            lock_done = True
            print("مقفول" if locked else "مفتوح")
    else:
        one_start = None
        lock_done = False

    # تنفيذ الأوامر (بس لو مفتوح)
    history = (history + [gesture])[-STABLE_FRAMES:]
    stable = len(history) == STABLE_FRAMES and len(set(history)) == 1

    if not locked and stable and gesture in ACTIONS:
        key, cooldown = ACTIONS[gesture]
        if now - last_fire.get(gesture, 0) > cooldown:
            pyautogui.press(key)
            last_fire[gesture] = now
            print("نفّذت:", gesture, "->", key)
            last_action = f"{gesture} -> {key}"
            last_action_time = now

    # التحكم المستمر في الصوت
    if not locked and gesture == "VOLUME MODE" and hand is not None:
        ratio = calculate_distance(hand[4], hand[8]) / calculate_distance(hand[5], hand[17])
        target = min(max((ratio - 0.3) / (1.5 - 0.3), 0), 1)
        smooth_vol = 0.7 * smooth_vol + 0.3 * target
        volume.SetMasterVolumeLevelScalar(smooth_vol, None)
        cv2.putText(frame, f"Volume: {int(smooth_vol * 100)}%", (20, 150),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 200, 255), 3)
    else:
        smooth_vol = volume.GetMasterVolumeLevelScalar()

    # العرض
    status = "LOCKED" if locked else "ACTIVE"
    color = (0, 0, 255) if locked else (0, 200, 0)
    cv2.putText(frame, gesture, (20, 50), cv2.FONT_HERSHEY_SIMPLEX,
                1.3, (255, 0, 0), 3)
    cv2.putText(frame, status, (20, 100), cv2.FONT_HERSHEY_SIMPLEX,
                1.0, color, 3)

    if now - last_action_time < 2:
        cv2.putText(frame, last_action, (20, 200), cv2.FONT_HERSHEY_SIMPLEX,
                    0.9, (0, 255, 255), 2)

    cv2.imshow("Live Gesture", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()