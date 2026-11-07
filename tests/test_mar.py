import numpy as np
import pytest
from vision.mouth_analyzer import mouth_aspect_ratio


def make_mouth(opening):
    pts = np.zeros((68, 2))
    pts[60], pts[64] = (0, 0), (10, 0)
    pts[61], pts[62], pts[63] = (3, -opening / 2), (5, -opening / 2), (7, -opening / 2)
    pts[67], pts[66], pts[65] = (3, opening / 2), (5, opening / 2), (7, opening / 2)
    return pts


def test_closed_mouth_zero():
    assert mouth_aspect_ratio(make_mouth(0)) == 0.0


def test_open_mouth_value():
    assert mouth_aspect_ratio(make_mouth(6)) == pytest.approx(0.6)


def test_bad_input():
    with pytest.raises(ValueError):
        mouth_aspect_ratio(np.zeros((10, 2)))
