"""Mouth Aspect Ratio (MAR) using the inner-lip points 60-67 (0-indexed).

Points: 60=left inner corner, 61/62/63=upper inner lip, 64=right inner corner,
65/66/67=lower inner lip. Pairs (61,67), (62,66), (63,65) are vertically opposite:
    MAR = (||p61-p67|| + ||p62-p66|| + ||p63-p65||) / (3 * ||p60-p64||)
Inner lips are used so ordinary lip thickness does not inflate the value.
Talking gives brief, small MAR rises; a yawn is a large, sustained one.
"""
import numpy as np

INNER_MOUTH = list(range(60, 68))


def mouth_aspect_ratio(landmarks: np.ndarray) -> float:
    pts = np.asarray(landmarks, dtype=float)
    if pts.shape[0] < 68:
        raise ValueError("expected 68 landmarks")
    horizontal = np.linalg.norm(pts[60] - pts[64])
    if horizontal == 0:
        return 0.0
    vertical = (np.linalg.norm(pts[61] - pts[67])
                + np.linalg.norm(pts[62] - pts[66])
                + np.linalg.norm(pts[63] - pts[65]))
    return float(vertical / (3.0 * horizontal))
