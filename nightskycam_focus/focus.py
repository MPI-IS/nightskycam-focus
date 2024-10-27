import logging
from dataclasses import dataclass
from typing import Dict, List, Tuple

import cv2
import matplotlib.pyplot as plt
import numpy as np
from camera_zwo_asi import ImageType
from camera_zwo_asi.camera import Camera

from .adapter import MAX_FOCUS, MIN_FOCUS, adapter, set_focus
from .process import gaussian2d_score, min_rayleigh


@dataclass
class FocusSweepConfig:
    step: int
    min_max: Tuple[int, int]
    pixel: Tuple[int, int]
    roi_size: Tuple[int, int]
    image_size: Tuple[int, int]
    exposure: int
    gain: int
    camera_index: int

    def get_range(self) -> List[int]:
        return list(range(self.min_max[0], self.min_max[1], self.step))

    def get_camera(self) -> Camera:
        camera = Camera(self.camera_index)
        camera.set_control("Exposure", self.exposure)
        camera.set_control("Gain", self.gain)
        roi = camera.get_roi()
        roi.bins = 1
        roi.start_x, roi.start_y = [
            p - s // 2 for p, s in zip(self.pixel, self.roi_size)
        ]
        roi.width, roi.height = self.roi_size
        roi.type = ImageType.rgb24
        camera.set_roi(roi)
        return camera


def find_focus(
    pixel: Tuple[int, int],
    size: Tuple[int, int],
    exposure: int = 50000,
    gain: int = 121,
    step: int = 20,
    min_focus: int = MIN_FOCUS,
    max_focus: int = MAX_FOCUS,
    camera_index: int = 0,
    image_size: Tuple[int, int] = (4144, 2822),
) -> Tuple[int, Dict[int, np.ndarray], np.ndarray]:

    config = FocusSweepConfig(
        step=step,
        min_max=(min_focus, max_focus),
        pixel=pixel,
        roi_size=size,
        exposure=exposure,
        gain=gain,
        camera_index=camera_index,
        image_size=image_size,
    )

    camera = config.get_camera()

    original_image = camera.capture().get_image()

    focus_score: Dict[int, float] = {}
    focus_image: Dict[int, np.ndarray] = {}

    logging.info("starting focus/aperture adapter")
    with adapter():
        for focus in config.get_range():
            set_focus(focus)
            last_focus = focus
            img = camera.capture().get_image()
            focus_image[focus] = img
            gray_img = cv2.cvtColor(img.astype(np.uint8), cv2.COLOR_BGR2GRAY)
            score = gaussian2d_score(gray_img)
            focus_score[focus] = score
            logging.info(f"evaluated focus: {focus} - score:\t{score:.2f}")

        logging.info("fitting rayleigh function")
        min_focus = min_rayleigh(focus_score)
        logging.info(f"best focus: {min_focus}")

        logging.info("capturing focused image")
        set_focus(min_focus)
        focused_image = camera.capture().get_image()

    return min_focus, focus_image, focused_image
