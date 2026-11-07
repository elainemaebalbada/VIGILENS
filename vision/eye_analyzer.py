"""Eye Aspect Ratio (EAR) using the 68-point landmark convention (0-indexed).

Right eye: points 36-41, left eye: points 42-47. Per eye the six points are
p1=outer corner, p2/p3=upper lid, p4=inner corner, p5/p6=lower lid:
    EAR = (||p2-p6|| + ||p3-p5||) / (2 * ||p1-p4||)
"""
import numpy as np

RIGHT_EYE = list(range(36, 42))
LEFT_EYE = list(range(42, 48))


def eye_aspect_ratio(eye: np.ndarray) -> float:
    """EAR for six (x, y) points ordered p1..p6."""
    eye = np.asarray(eye, dtype=float)
    if eye.shape != (6, 2):
        raise ValueError("eye must have shape (6, 2)")
    horizontal = np.linalg.norm(eye[0] - eye[3])
    if horizontal == 0:
        return 0.0
    vertical = np.linalg.norm(eye[1] - eye[5]) + np.linalg.norm(eye[2] - eye[4])
    return float(vertical / (2.0 * horizontal))


def average_ear(landmarks: np.ndarray):
    """Return (left_ear, right_ear, average) from a (68, 2) landmark array."""
    left = eye_aspect_ratio(landmarks[LEFT_EYE])
    right = eye_aspect_ratio(landmarks[RIGHT_EYE])
    return left, right, (left + right) / 2.0
