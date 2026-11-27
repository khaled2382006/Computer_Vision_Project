import os
import math
import time
import ctypes
import urllib.request
from ctypes import cast, POINTER

import cv2
import mediapipe as mp
import pyautogui
import streamlit as st
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

# ===== Page Configuration & Styling =====
st.set_page_config(
    page_title="Gesture Media Controller",
    page_icon="✋",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        .block-container {
            padding-top: 1.6rem;
            padding-bottom: 1.5rem;
        }
        div[data-testid="stMetric"] {
            background-color: rgba(128, 128, 128, 0.08);
            border: 1px solid rgba(128, 128, 128, 0.2);
            padding: 0.75rem 1rem;
            border-radius: 0.6rem;
        }
        .guide-card {
            background-color: rgba(128, 128, 128, 0.06);
            border: 1px solid rgba(128, 128, 128, 0.18);
            border-radius: 0.65rem;
            padding: 0.85rem 1rem;
            margin-bottom: 0.6rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# ===== Constants =====
HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20), (0, 17),
]

ACTIONS = {
    "OPEN PALM": ("playpause", 1.5),
    "THUMBS UP": ("volumeup", 0.3),
    "THUMBS DOWN": ("volumedown", 0.3),
    "OK SIGN": ("volumemute", 1.5),
    "TWO FINGERS": ("nexttrack", 1.5),
    "THREE FINGERS": ("prevtrack", 1.5),
}

GESTURE_GUIDE = [
    ("☝️", "One Finger (Hold)", "Lock or unlock hand control so accidental moves do not trigger actions."),
    ("✋", "Open Palm", "Play or pause the video or audio."),
    ("👍", "Thumbs Up", "Turn volume up."),
    ("👎", "Thumbs Down", "Turn volume down."),
    ("👌", "OK Sign", "Mute or unmute sound."),
    ("✌️", "Two Fingers", "Go to the next video or track."),
    ("3️⃣", "Three Fingers", "Go to the previous video or track."),
    ("🔊", "Thumb + Index", "Adjust volume smoothly by moving thumb and index apart or together."),
]


# ===== Resource Helpers =====
def create_detector():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(base_dir, "hand_landmarker.task")
    model_url = (
        "https://storage.googleapis.com/mediapipe-models/"
        "hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
    )

    if not os.path.exists(model_path):
        urllib.request.urlretrieve(model_url, model_path)

    with open(model_path, "rb") as f:
        model_bytes = f.read()

    options = vision.HandLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_buffer=model_bytes),
        running_mode=vision.RunningMode.VIDEO,
        num_hands=1,
        min_hand_detection_confidence=0.6,
        min_tracking_confidence=0.6,
    )
    return vision.HandLandmarker.create_from_options(options)


@st.cache_resource
def load_volume_controller():
    speakers = AudioUtilities.GetSpeakers()
    try:
        return speakers.EndpointVolume
    except AttributeError:
        interface = speakers.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return cast(interface, POINTER(IAudioEndpointVolume))


# ===== Geometry & Gesture Recognition =====
def calculate_distance(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def count_fingers(lm):
    wrist = lm[0]
    tips = [8, 12, 16, 20]
    pips = [6, 10, 14, 18]
    return [
        1 if calculate_distance(lm[t], wrist) > calculate_distance(lm[p], wrist) * 1.1 else 0
        for t, p in zip(tips, pips)
    ]


def detect_thumb(lm):
    palm_width = calculate_distance(lm[5], lm[17])
    away_from_pinky = calculate_distance(lm[4], lm[17]) > calculate_distance(lm[3], lm[17]) * 1.05
    away_from_index = calculate_distance(lm[4], lm[5]) > palm_width * 0.7
    return away_from_pinky and away_from_index


def recognize_gesture_v2(lm):
    fingers = count_fingers(lm)
    thumb_open = detect_thumb(lm)
    total = sum(fingers)
    palm_width = calculate_distance(lm[5], lm[17])
    hand_size = calculate_distance(lm[0], lm[9])
    thumb_tip, wrist = lm[4], lm[0]

    pinch = calculate_distance(lm[4], lm[8]) / hand_size
    others_up = 0
    for tip, pip in [(12, 10), (16, 14), (20, 18)]:
        if calculate_distance(lm[tip], lm[0]) > calculate_distance(lm[pip], lm[0]):
            others_up += 1
    if pinch < 0.35 and others_up >= 2:
        return "OK SIGN"

    if thumb_open and total == 0:
        if thumb_tip.y < wrist.y - palm_width * 0.5:
            return "THUMBS UP"
        if thumb_tip.y > wrist.y + palm_width * 0.5:
            return "THUMBS DOWN"

    if thumb_open and fingers == [1, 0, 0, 0]:
        return "VOLUME MODE"

    if total == 4:
        return "OPEN PALM"
    if total == 0:
        return "CLOSED FIST"
    if total == 1:
        return "ONE FINGER"
    if total == 2:
        return "TWO FINGERS"
    if total == 3:
        return "THREE FINGERS"
    return "UNKNOWN"


def is_youtube_active():
    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return "youtube" in buf.value.lower()


# ===== Session State Initialization =====
if "running" not in st.session_state:
    st.session_state.running = False
if "locked" not in st.session_state:
    st.session_state.locked = True
if "history" not in st.session_state:
    st.session_state.history = []
if "last_fire" not in st.session_state:
    st.session_state.last_fire = {}
if "one_start" not in st.session_state:
    st.session_state.one_start = None
if "lock_done" not in st.session_state:
    st.session_state.lock_done = False
if "last_action" not in st.session_state:
    st.session_state.last_action = "None"
if "last_action_time" not in st.session_state:
    st.session_state.last_action_time = 0.0
if "start_time" not in st.session_state:
    st.session_state.start_time = time.time()
if "last_ts" not in st.session_state:
    st.session_state.last_ts = 0

volume = load_volume_controller()
if "smooth_vol" not in st.session_state:
    st.session_state.smooth_vol = volume.GetMasterVolumeLevelScalar()

# ===== Header =====
st.title("Gesture Media Controller")
st.caption("Control videos, music, and volume with simple hand gestures.")

# ===== Sidebar Controls =====
with st.sidebar:
    st.header("Controls")
    col_start, col_stop = st.columns(2)
    if col_start.button("Start", type="primary", use_container_width=True):
        st.session_state.running = True
        st.session_state.start_time = time.time()
        st.session_state.last_ts = 0
    if col_stop.button("Stop", use_container_width=True):
        st.session_state.running = False

    lock_btn_label = "Unlock Gesture Control" if st.session_state.locked else "Lock Gesture Control"
    if st.button(lock_btn_label, use_container_width=True):
        st.session_state.locked = not st.session_state.locked
        st.session_state.one_start = None
        st.session_state.lock_done = False

    st.divider()
    st.subheader("Fine-Tuning")
    stable_frames = st.slider(
        "Gesture Smoothness (Frames)",
        min_value=3,
        max_value=15,
        value=5,
        help="Higher means fewer accidental triggers, but you hold the gesture slightly longer.",
    )
    hold_seconds = st.slider(
        "Hold to Lock/Unlock (sec)",
        min_value=0.5,
        max_value=3.0,
        value=1.5,
        step=0.1,
        help="How many seconds to hold one finger up to switch between Locked and Active.",
    )

# ===== Live Status Metrics & Camera Feed =====
status_col, gesture_col, action_col = st.columns(3)
status_metric = status_col.empty()
gesture_metric = gesture_col.empty()
action_metric = action_col.empty()

status_metric.metric("Status", "LOCKED" if st.session_state.locked else "ACTIVE")
gesture_metric.metric("Current Gesture", "NO HAND")
action_metric.metric("Last Action", st.session_state.last_action)

frame_placeholder = st.empty()

# ===== Gesture Guide =====
with st.expander("Gesture Guide", expanded=False):
    st.write(
        "1. Click **Start** in the sidebar. "
        "2. Unlock control by holding **One Finger** up (or clicking **Unlock Gesture Control**). "
        "3. Switch to your video or media player and use the gestures below:"
    )
    for icon, name, desc in GESTURE_GUIDE:
        st.markdown(
            f"""
            <div class="guide-card">
                <span style="font-size: 1.35rem; margin-right: 0.5rem;">{icon}</span>
                <strong>{name}</strong> &mdash; <span>{desc}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ===== Main Capture Loop =====
if st.session_state.running:
    detector = create_detector()
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    if not cap.isOpened():
        st.error("Could not open the camera. Make sure no other app is using it.")
        st.session_state.running = False
        detector.close()
    else:
        st.session_state.start_time = time.time()
        st.session_state.last_ts = 0
        try:
            while st.session_state.running:
                ok, frame = cap.read()
                if not ok:
                    st.warning("Could not read a frame from the camera.")
                    break

                frame = cv2.flip(frame, 1)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

                elapsed_ms = int((time.time() - st.session_state.start_time) * 1000)
                timestamp = max(elapsed_ms, st.session_state.last_ts + 1)
                st.session_state.last_ts = timestamp

                try:
                    result = detector.detect_for_video(mp_image, timestamp)
                except ValueError:
                    detector.close()
                    detector = create_detector()
                    st.session_state.start_time = time.time()
                    st.session_state.last_ts = 1
                    result = detector.detect_for_video(mp_image, 1)

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

                if gesture == "ONE FINGER":
                    if st.session_state.one_start is None:
                        st.session_state.one_start = now
                    elif not st.session_state.lock_done and now - st.session_state.one_start >= hold_seconds:
                        st.session_state.locked = not st.session_state.locked
                        st.session_state.lock_done = True
                else:
                    st.session_state.one_start = None
                    st.session_state.lock_done = False

                st.session_state.history = (st.session_state.history + [gesture])[-stable_frames:]
                stable = (
                    len(st.session_state.history) == stable_frames
                    and len(set(st.session_state.history)) == 1
                )

                if not st.session_state.locked and stable and gesture in ACTIONS:
                    key, cooldown = ACTIONS[gesture]
                    if now - st.session_state.last_fire.get(gesture, 0) > cooldown:
                        yt_active = is_youtube_active()
                        if gesture == "TWO FINGERS":
                            if yt_active:
                                pyautogui.hotkey("shift", "n")
                            else:
                                pyautogui.press("nexttrack")
                        elif gesture == "THREE FINGERS":
                            if yt_active:
                                pyautogui.hotkey("shift", "p")
                            else:
                                pyautogui.press("prevtrack")
                        else:
                            pyautogui.press(key)

                        st.session_state.last_fire[gesture] = now
                        st.session_state.last_action = f"{gesture} -> {key}"
                        st.session_state.last_action_time = now

                if not st.session_state.locked and gesture == "VOLUME MODE" and hand is not None:
                    ratio = calculate_distance(hand[4], hand[8]) / calculate_distance(hand[5], hand[17])
                    target = min(max((ratio - 0.3) / (1.5 - 0.3), 0), 1)
                    st.session_state.smooth_vol = 0.7 * st.session_state.smooth_vol + 0.3 * target
                    volume.SetMasterVolumeLevelScalar(st.session_state.smooth_vol, None)
                    cv2.putText(
                        frame,
                        f"Volume: {int(st.session_state.smooth_vol * 100)}%",
                        (20, 150),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1.0,
                        (0, 200, 255),
                        3,
                    )
                else:
                    st.session_state.smooth_vol = volume.GetMasterVolumeLevelScalar()

                status_text = "LOCKED" if st.session_state.locked else "ACTIVE"
                status_color = (0, 0, 255) if st.session_state.locked else (0, 200, 0)
                cv2.putText(frame, gesture, (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.3, (255, 0, 0), 3)
                cv2.putText(frame, status_text, (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.0, status_color, 3)

                if now - st.session_state.last_action_time < 2:
                    cv2.putText(
                        frame,
                        st.session_state.last_action,
                        (20, 200),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.9,
                        (0, 255, 255),
                        2,
                    )

                status_metric.metric("Status", status_text)
                gesture_metric.metric("Current Gesture", gesture)
                action_metric.metric("Last Action", st.session_state.last_action)

                rgb_display = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame_placeholder.image(rgb_display, channels="RGB", use_container_width=True)
                time.sleep(0.02)
        finally:
            cap.release()
            detector.close()
else:
    st.info("Click **Start** in the sidebar to turn on the camera.")