"""Webcam access with clear errors. Windows uses the DirectShow backend first
because the default backend is slow to open and sometimes fails."""
import sys
import time
from typing import List, Optional, Tuple

import cv2


class CameraUnavailableError(RuntimeError):
    pass


def _backends() -> list:
    if sys.platform.startswith("win"):
        return [cv2.CAP_DSHOW, cv2.CAP_ANY]
    return [cv2.CAP_ANY]


class CameraService:
    def __init__(self, index: int = 0):
        self.index = index
        self._cap: Optional[cv2.VideoCapture] = None

    @property
    def is_open(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    def open(self) -> None:
        self.release()
        for backend in _backends():
            cap = cv2.VideoCapture(self.index, backend)
            if not cap.isOpened():
                cap.release()
                continue
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            for _ in range(10):  # cameras often return empty frames while warming up
                ok, frame = cap.read()
                if ok and frame is not None:
                    self._cap = cap
                    return
                time.sleep(0.1)
            cap.release()
        raise CameraUnavailableError(
            f"Camera {self.index} could not be opened. Check that it is plugged in, "
            "not used by another program (Zoom, Teams, browser), and that Windows "
            "camera privacy settings allow desktop apps.")

    def read(self) -> Tuple[bool, Optional["cv2.typing.MatLike"]]:
        if self._cap is None:
            return False, None
        try:
            return self._cap.read()
        except cv2.error:
            return False, None

    def release(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            finally:
                self._cap = None

    @staticmethod
    def list_available(max_index: int = 5) -> List[int]:
        """Probe camera indices 0..max_index-1. Cameras currently in use by
        monitoring cannot be probed, so call this only while stopped."""
        found = []
        for index in range(max_index):
            for backend in _backends():
                cap = cv2.VideoCapture(index, backend)
                opened = cap.isOpened()
                cap.release()
                if opened:
                    found.append(index)
                    break
        return found
