"""dlib 68-point landmark detection inside a Haar-detected face box."""
import os
import numpy as np

MODEL_FILENAME = "shape_predictor_68_face_landmarks.dat"
DEFAULT_MODEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", MODEL_FILENAME)


class LandmarkModelError(RuntimeError):
    pass


class LandmarkDetector:
    def __init__(self, model_path: str = DEFAULT_MODEL_PATH):
        try:
            import dlib
        except ImportError as exc:
            raise LandmarkModelError(
                "dlib is not installed. See README (Windows install section).") from exc
        if not os.path.isfile(model_path):
            raise LandmarkModelError(
                f"Landmark model not found at:\n{model_path}\n"
                "Download shape_predictor_68_face_landmarks.dat.bz2 from "
                "https://dlib.net/files/, extract it, and place the .dat file in 'models/'.")
        self._dlib = dlib
        self._predictor = dlib.shape_predictor(model_path)

    def detect(self, gray, face_box):
        """Return a (68, 2) int array, or None on failure."""
        x, y, w, h = face_box
        rect = self._dlib.rectangle(x, y, x + w, y + h)
        try:
            shape = self._predictor(gray, rect)
        except Exception:
            return None
        if shape.num_parts != 68:
            return None
        return np.array([(p.x, p.y) for p in shape.parts()], dtype=int)
