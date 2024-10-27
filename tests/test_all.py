from pathlib import Path
from typing import Callable, Dict, NewType

import cv2
import numpy as np
from nightskycam_focus.process import (brenner_score, gaussian2d_score,
                                       laplacian_score, min_rayleigh,
                                       sobel_score)

_IMAGES_FOLDER = Path(__file__).parent.absolute() / "images"
MIN_FOCUS = 470

Focus = NewType("Focus", int)


def _read_images() -> Dict[Focus, np.ndarray]:
    npy_files = list(_IMAGES_FOLDER.glob("*.npy"))
    return {
        int(Focus(Path(f).stem)): np.load(str(f)) for f in npy_files  # type: ignore
    }


def _compute_focus_score(
    f: Callable[
        [
            np.ndarray,
        ],
        float,
    ]
) -> Dict[int, float]:
    focus_score: Dict[int, float] = {}

    focus_images = _read_images()
    for focus, image in focus_images.items():
        gray_img = cv2.cvtColor(image.astype(np.uint8), cv2.COLOR_BGR2GRAY)
        score = f(gray_img)
        focus_score[focus] = score

    return focus_score


def test_gaussian_2d_score():

    focus_score = _compute_focus_score(gaussian2d_score)
    focus = list(sorted(focus_score.keys()))

    for f1, f2 in zip(focus, focus[1:]):
        if f1 < MIN_FOCUS:
            assert focus_score[f1] > focus_score[f2]

        else:
            assert focus_score[f1] < focus_score[f2]


def test_min_rayleigh():

    focus_score = _compute_focus_score(gaussian2d_score)
    focus = list(sorted(focus_score.keys()))
    min_index = focus.index(MIN_FOCUS)
    rayleigh_min_focus = min_rayleigh(focus_score)
    assert rayleigh_min_focus > focus[min_index - 1]
    assert rayleigh_min_focus < focus[min_index + 1]
