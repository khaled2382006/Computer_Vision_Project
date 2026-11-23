from collections import deque
import time
import pyautogui


class SlidesController:
    """
    Controls presentation slides and video playback
    using hand gestures detected by MediaPipe.
    """

    def __init__(self):

        # Palm position tracking
        self.positions = deque(maxlen=10)

        # General action cooldown
        self.cooldown = 1.0
        self.last_action_time = 0.0

        # Swipe detection settings
        self.swipe_threshold = 0.15
        self.swipe_cooldown = 0.8
        self.last_swipe_time = 0.0

        # Open palm hold settings
        self.hold_duration = 1.0
        self.hold_start_time = None
        self.hold_anchor = None
        self.hold_triggered = False

        # Palm stability threshold
        self.stability_threshold = 0.03

        # PyAutoGUI configuration
        pyautogui.PAUSE = 0.1

    # -----------------------------------------
    # 1. Extract Palm Position
    # -----------------------------------------

    def get_palm_position(self, landmarks):

        if landmarks is None or len(landmarks) < 18:
            return None

        palm_points = [0, 5, 9, 13, 17]

        x_values = []
        y_values = []

        for index in palm_points:

            point = landmarks[index]

            if isinstance(point, dict):
                x = point["x"]
                y = point["y"]

            else:
                x = point.x
                y = point.y

            x_values.append(x)
            y_values.append(y)

        palm_x = sum(x_values) / len(x_values)
        palm_y = sum(y_values) / len(y_values)

        return palm_x, palm_y

    # -----------------------------------------
    # 2. Check Action Cooldown
    # -----------------------------------------

    def can_perform_action(self):

        current_time = time.monotonic()

        if current_time - self.last_action_time >= self.cooldown:

            self.last_action_time = current_time
            return True

        return False

    # -----------------------------------------
    # 3. Reset Hold State
    # -----------------------------------------

    def reset_hold(self):

        self.hold_start_time = None
        self.hold_anchor = None
        self.hold_triggered = False

    # -----------------------------------------
    # 4. Execute Keyboard Action
    # -----------------------------------------

    def execute_action(self, action):

        if not self.can_perform_action():
            return None

        if action == "NEXT_SLIDE":

            pyautogui.press("right")
            print("Next Slide")

        elif action == "PREVIOUS_SLIDE":

            pyautogui.press("left")
            print("Previous Slide")

        elif action == "PLAY_PAUSE":

            pyautogui.press("space")
            print("Play / Pause")

        else:
            return None

        return action

    # -----------------------------------------
    # 5. Detect Swipe
    # -----------------------------------------

    def detect_swipe(self):

        if len(self.positions) < 10:
            return None

        current_time = time.monotonic()

        # Prevent rapid repeated swipes
        if current_time - self.last_swipe_time < self.swipe_cooldown:
            return None

        first_x, first_y = self.positions[0]
        last_x, last_y = self.positions[-1]

        movement_x = last_x - first_x
        movement_y = last_y - first_y

        # Minimum horizontal movement
        if abs(movement_x) < self.swipe_threshold:
            return None

        # Reject diagonal movements
        if abs(movement_x) < abs(movement_y) * 1.5:
            return None

        self.last_swipe_time = current_time

        if movement_x > 0:
            return "NEXT_SLIDE"

        return "PREVIOUS_SLIDE"

    # -----------------------------------------
    # 6. Detect Open Palm Hold
    # -----------------------------------------

    def detect_hold(self, palm_position):

        current_time = time.monotonic()

        palm_x, palm_y = palm_position

        if self.hold_start_time is None:

            self.hold_start_time = current_time
            self.hold_anchor = palm_position

            return None

        anchor_x, anchor_y = self.hold_anchor

        movement_x = abs(palm_x - anchor_x)
        movement_y = abs(palm_y - anchor_y)

        # Check palm stability
        if (
            movement_x > self.stability_threshold
            or movement_y > self.stability_threshold
        ):

            self.hold_start_time = current_time
            self.hold_anchor = palm_position

            return None

        elapsed_time = current_time - self.hold_start_time

        if elapsed_time >= self.hold_duration:

            if not self.hold_triggered:

                self.hold_triggered = True
                return "PLAY_PAUSE"

        return None

    # -----------------------------------------
    # 7. Main Update Function
    # -----------------------------------------

    def update(self, landmarks, gesture):

        if gesture is None:
            gesture = ""

        gesture = gesture.lower().replace(" ", "_")

        # Only process open palm gesture
        if gesture != "open_palm":

            self.positions.clear()
            self.reset_hold()

            return None

        # Extract palm position
        palm_position = self.get_palm_position(landmarks)

        if palm_position is None:

            self.positions.clear()
            self.reset_hold()

            return None

        # Store palm position
        self.positions.append(palm_position)

        # Detect swipe
        swipe_action = self.detect_swipe()

        if swipe_action:

            action = self.execute_action(swipe_action)

            if action:

                self.positions.clear()
                self.reset_hold()

                return action

        # Detect hold
        hold_action = self.detect_hold(palm_position)

        if hold_action:

            return self.execute_action(hold_action)

        return None
