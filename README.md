# Hand Gesture Media Controller

Control your computer's media playback and volume with hand gestures,
using your webcam. Built with Python, MediaPipe, and OpenCV.

## Demo
[Watch the demo](demo.mp4)

## Features
- Real-time hand landmark detection (21 points) with MediaPipe HandLandmarker
- Rule-based gesture recognition using landmark distances,
  so it still works when the hand is tilted or rotated
- Lock/unlock mode to prevent accidental commands
- Gesture stability check (5 consecutive frames) and per-command cooldowns
- Continuous volume control by the distance between thumb and index finger
- On-screen status: current gesture, lock state, last executed command

## Gestures

| Gesture | Action |
|---|---|
| Index finger held for 1.5 s | Lock / unlock |
| Open palm | Play / pause |
| Thumbs up / down | Volume up / down (steps) |
| Thumb + index (L shape) | Continuous volume control |
| OK sign | Mute |
| Two fingers | Next track |
| Three fingers | Previous track |

Commands only run while the status shows **ACTIVE**.

## Installation
```bash
pip install -r requirements.txt
python live_gesture.py
```
The hand landmarker model downloads automatically on first run.
Press **Q** in the camera window to quit.

## Requirements
- Windows (volume control uses `pycaw`)
- A webcam
- Python 3.9+

## How it works
1. OpenCV captures webcam frames.
2. MediaPipe returns 21 hand landmarks per frame.
3. A finger counts as extended if its tip is farther from the wrist
   than its middle joint.
4. The gesture is classified from the extended fingers and thumb position.
5. A stable gesture triggers a media key via `pyautogui`, or sets the
   system volume via `pycaw`.

## Limitations
- Windows only
- Rule-based classification can confuse similar gestures under poor
  lighting or at extreme angles
- Media next/previous works only with players that respond to media keys

## Possible improvements
- Train a small classifier on collected landmark data
- Support more than one hand
- Cross-platform volume control