import numpy as np
import pytest
from vision.eye_analyzer import eye_aspect_ratio, average_ear


def test_open_eye_value():
    eye = np.array([[0, 0], [1, 1], [3, 1], [4, 0], [3, -1], [1, -1]])
    assert eye_aspect_ratio(eye) == pytest.approx(0.5)


def test_closed_eye_is_zero():
    eye = np.array([[0, 0], [1, 0], [3, 0], [4, 0], [3, 0], [1, 0]])
    assert eye_aspect_ratio(eye) == 0.0


def test_degenerate_and_bad_shape():
    assert eye_aspect_ratio(np.zeros((6, 2))) == 0.0
    with pytest.raises(ValueError):
        eye_aspect_ratio(np.zeros((5, 2)))


def test_average_ear_uses_correct_indices():
    pts = np.zeros((68, 2))
    for start in (36, 42):
        pts[start:start + 6] = [[0, 0], [1, 1], [3, 1], [4, 0], [3, -1], [1, -1]]
    l, r, avg = average_ear(pts)
    assert l == pytest.approx(0.5) and r == pytest.approx(0.5) and avg == pytest.approx(0.5)
