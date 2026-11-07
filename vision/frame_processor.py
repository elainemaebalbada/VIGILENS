"""Per-frame pipeline: resize -> grayscale -> Haar -> dlib -> EAR/MAR -> annotate."""
from dataclasses import dataclass
from typing import Optional
import cv2
import numpy as np

from vision.face_detector import FaceDetector
from vision.landmark_detector import LandmarkDetector
from vision.eye_analyzer import average_ear, LEFT_EYE, RIGHT_EYE
from vision.mouth_analyzer import mouth_aspect_ratio, INNER_MOUTH

PROCESS_WIDTH = 640  # consistent processing size


@dataclass
class FrameResult:
    frame: np.ndarray               # annotated BGR frame
    face_found: bool = False
    ear: Optional[float] = None
    mar: Optional[float] = None


class FrameProcessor:
    def __init__(self, face_detector: FaceDetector = None,
                 landmark_detector: LandmarkDetector = None):
        self.faces = face_detector or FaceDetector()
        self.landmarks = landmark_detector or LandmarkDetector()

    def process(self, frame_bgr) -> FrameResult:
        h, w = frame_bgr.shape[:2]
        if w != PROCESS_WIDTH:
            frame_bgr = cv2.resize(
                frame_bgr, (PROCESS_WIDTH, int(h * PROCESS_WIDTH / w)))
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)  # helps in uneven lighting
        result = FrameResult(frame=frame_bgr)

        box = self.faces.detect(gray)
        if box is None:
            return result
        x, y, bw, bh = box
        cv2.rectangle(frame_bgr, (x, y), (x + bw, y + bh), (208, 219, 142), 2)

        pts = self.landmarks.detect(gray, box)
        if pts is None:
            return result
        result.face_found = True
        _, _, result.ear = average_ear(pts)
        result.mar = mouth_aspect_ratio(pts)
        for idx_group in (LEFT_EYE, RIGHT_EYE, INNER_MOUTH):
            contour = pts[idx_group].reshape(-1, 1, 2)
            cv2.polylines(frame_bgr, [contour], True, (208, 219, 142), 1)
            for px, py in pts[idx_group]:
                cv2.circle(frame_bgr, (int(px), int(py)), 2, (0, 200, 255), -1)
        return result
