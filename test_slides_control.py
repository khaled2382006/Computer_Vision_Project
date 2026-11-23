
import time
from unittest.mock import patch

from slides_control import SlidesController


def test_palm_position():

    controller = SlidesController()

    # Simulated MediaPipe landmarks
    landmarks = [
        {"x": 0.5, "y": 0.5, "z": 0.0}
        for _ in range(21)
    ]

    position = controller.get_palm_position(landmarks)

    assert position == (0.5, 0.5)

    print("PASS: Palm position detection")


def test_next_slide():

    controller = SlidesController()

    with patch("slides_control.pyautogui.press") as mock_press:

        result = controller.execute_action("NEXT_SLIDE")

        assert result == "NEXT_SLIDE"
        mock_press.assert_called_once_with("right")

    print("PASS: Next slide action")


def test_previous_slide():

    controller = SlidesController()

    with patch("slides_control.pyautogui.press") as mock_press:

        result = controller.execute_action("PREVIOUS_SLIDE")

        assert result == "PREVIOUS_SLIDE"
        mock_press.assert_called_once_with("left")

    print("PASS: Previous slide action")


def test_play_pause():

    controller = SlidesController()

    with patch("slides_control.pyautogui.press") as mock_press:

        result = controller.execute_action("PLAY_PAUSE")

        assert result == "PLAY_PAUSE"
        mock_press.assert_called_once_with("space")

    print("PASS: Play/Pause action")


def test_swipe_detection():

    controller = SlidesController()

    # Simulate movement to the right
    controller.positions.extend([
        (0.10 + i * 0.02, 0.5)
        for i in range(10)
    ])

    result = controller.detect_swipe()

    assert result == "NEXT_SLIDE"

    print("PASS: Swipe right detection")


def test_hold_detection():

    controller = SlidesController()

    controller.hold_start_time = time.monotonic() - 1.2
    controller.hold_anchor = (0.5, 0.5)

    result = controller.detect_hold((0.5, 0.5))

    assert result == "PLAY_PAUSE"

    print("PASS: Open palm hold detection")


if __name__ == "__main__":

    test_palm_position()
    test_next_slide()
    test_previous_slide()
    test_play_pause()
    test_swipe_detection()
    test_hold_detection()

    print("\nAll tests passed successfully!")
