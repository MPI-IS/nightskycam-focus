from pathlib import Path
import argparse
import logging
import sys
from typing import Tuple

import cv2
import numpy as np
from camera_zwo_asi import ImageType
from camera_zwo_asi.camera import Camera
from camera_zwo_asi.image import Image

from .adapter import adapter, set_focus, set_aperture, Aperture
from .focus import find_focus


def _get_pixel_from_user(
    image: np.ndarray, resize: int = 4
) -> Tuple[int, int]:
    down_sized_image = cv2.resize(
        image, (image.shape[1] // resize, image.shape[0] // resize)
    )

    cv2.namedWindow("Select Pixel")

    clicked_pixel = (0, 0)

    def _click_event(event, x, y, flags, param):
        nonlocal clicked_pixel
        if event == cv2.EVENT_LBUTTONDOWN:
            clicked_pixel = (x, y)
            cv2.destroyAllWindows()

    cv2.setMouseCallback("Select Pixel", _click_event)
    cv2.imshow("Select Pixel", down_sized_image)
    cv2.waitKey(0)

    if not clicked_pixel:
        raise RuntimeError("No pixel was selected.")

    full_size_pixel = (clicked_pixel[0] * resize, clicked_pixel[1] * resize)

    return full_size_pixel


def _capture(exposure: int, gain: int, camera_index: int) -> Image:
    camera = Camera(camera_index)
    camera.set_control("Exposure", exposure)
    camera.set_control("Gain", gain)
    roi = camera.get_roi()
    roi.bins = 1
    roi.type = ImageType.rgb24
    camera.set_roi(roi)
    return camera.capture()


def _get_full_image(exposure: int, gain: int, camera_index: int) -> np.ndarray:
    image = _capture(exposure, gain, camera_index)
    return image.get_image()


def _add_border(img: np.array, thickness: int = 5, color=(255, 0, 0)):
    new_height = img.shape[0] - 2 * thickness
    new_width = img.shape[1] - 2 * thickness
    cropped_img = img[
        thickness : thickness + new_height, thickness : thickness + new_width
    ]
    bordered_img = cv2.copyMakeBorder(
        cropped_img,
        thickness,
        thickness,
        thickness,
        thickness,
        cv2.BORDER_CONSTANT,
        value=color,
    )
    return bordered_img


def _zwo_asi_focus_sweep():

    parser = argparse.ArgumentParser(
        description="Focus sweep on zwo-asi camera"
    )
    parser.add_argument(
        "--camera_index",
        type=int,
        default=0,
        help="Camera index (default: %(default)s)",
    )
    parser.add_argument(
        "--roi_size",
        type=int,
        nargs=2,
        default=(104, 104),
        help="ROI size (width, height) (default: %(default)s)",
    )
    parser.add_argument(
        "--exposure",
        type=int,
        default=50000,
        help="Camera exposure (default: %(default)s)",
    )
    parser.add_argument(
        "--gain",
        type=int,
        default=121,
        help="Camera gain (default: %(default)s)",
    )
    parser.add_argument(
        "--step",
        type=int,
        default=20,
        help="Focus step size (default: %(default)s)",
    )
    parser.add_argument("--show", action="store_true", help="Show the image")
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save the image (focus.png in current directory)",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="More info in the terminal"
    )
    parser.add_argument(
        "--silent",
        action="store_true",
        help="No info in the terminal, except for the minimum focus",
    )

    args = parser.parse_args()

    # setting the logs
    if args.verbose:
        logging.basicConfig(
            level=logging.DEBUG, format="focus sweep: %(message)s"
        )
    elif args.silent:
        ...
    else:
        logging.basicConfig(
            level=logging.INFO, format="focus sweep: %(message)s"
        )

    logging.info(
        f"capturing image (exposure: {args.exposure}, gain: {args.gain})"
    )
    full_image = _get_full_image(args.exposure, args.gain, args.camera_index)

    logging.info("prompting user for target pixel")
    pixel = _get_pixel_from_user(full_image)

    logging.info(
        f"focus sweep on target pixel {repr(pixel)} (window size: {repr(args.roi_size)})"
    )
    focus, focus_image, focused_image = find_focus(
        pixel=pixel,
        size=tuple(args.roi_size),
        exposure=args.exposure,
        gain=args.gain,
        step=args.step,
        camera_index=args.camera_index,
    )

    print(f"Focus: {focus}")

    # all the images
    images = [focus_image[f] for f in sorted(focus_image.keys())]

    # the best focus image with border
    focused_image = _add_border(focused_image)

    # all images in a row
    concatenated_images = np.concatenate(images + [focused_image], axis=1)

    if args.show:
        cv2.imshow("Focus", concatenated_images)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    if args.save:
        cv2.imwrite("focus.png", concatenated_images)


def zwo_asi_focus_sweep():
    try:
        _zwo_asi_focus_sweep()
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def zwo_asi_focus_test():
    logging.basicConfig(level=logging.DEBUG, format="focus test: %(message)s")
    with adapter():
        logging.info("adapter running")


def _check_range(value: int, minimum: int = 350, maximum: int = 650) -> int:
    """Check if the input value is an integer within the range 350 to 650."""
    try:
        ivalue = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value} is not a valid integer")
    if ivalue < minimum or ivalue > maximum:
        raise argparse.ArgumentTypeError(
            f"{value} is an invalid value. Must be between {minimum} and {maximum}."
        )
    return ivalue


def _valid_aperture(value: str) -> Aperture:
    try:
        return Aperture.get(value)
    except KeyError:
        raise argparse.ArgumentTypeError(
            f"{value} is not a valid aperture. Valid apertures: MAX (open), V1, ..., V10, MIN (closed)"
        )


def zwo_asi_focus():
    logging.basicConfig(level=logging.DEBUG, format="focus: %(message)s")
    parser = argparse.ArgumentParser(
        description="Focus change on zwo-asi camera"
    )
    parser.add_argument(
        "focus",
        type=_check_range,
        help="desired focus. int between 350 and 650",
    )
    parser.add_argument(
        "--aperture",
        type=_valid_aperture,
        help="desired aperture. MAX: open, MIN: close, V1 ... V10: intermediate values",
        required=False,
    )
    parser.add_argument(
        "--exposure",
        type=int,
        help="if set (microseconds), a picture will be taken and saved in the current directory",
        required=False,
    )
    args = parser.parse_args()
    with adapter():
        logging.info(f"setting focus to {args.focus}")
        set_focus(args.focus)
        if args.aperture is not None:
            logging.info(f"setting aperture to {args.aperture}")
            set_aperture(args.aperture)
    if args.exposure is None:
        return
    logging.info(f"taking picture with exposure {args.exposure}")
    image = _capture(args.exposure, 121, 0)
    if args.aperture:
        filename = f"img_{args.focus}_{args.aperture}_{args.exposure}.tiff"
    else:
        filename = f"img_{args.focus}_{args.exposure}.tiff"
    filepath = str(Path.cwd() / filename)
    logging.info(f"saving image to {filepath}")
    image.save(filepath)
