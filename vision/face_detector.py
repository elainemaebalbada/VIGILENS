"""Haar Cascade face detection (single face, largest wins)."""
import os
import cv2


class FaceDetector:
    def __init__(self, cascade_path: str = None):
        path = cascade_path or os.path.join(
            cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
        self._cascade = cv2.CascadeClassifier(path)
        if self._cascade.empty():
            raise FileNotFoundError(f"Could not load Haar cascade: {path}")

    def detect(self, gray):
        """Return (x, y, w, h) of the largest face, or None."""
        faces = self._cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80))
        if len(faces) == 0:
            return None
        return tuple(int(v) for v in max(faces, key=lambda f: f[2] * f[3]))
