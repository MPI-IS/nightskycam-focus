import argparse
import logging
import sys
from pathlib import Path

from camera_zwo_asi import ImageType
from camera_zwo_asi.camera import Camera
from camera_zwo_asi.image import Image

from . import adapter

logger = logging.getLogger(__name__)

def _capture(exposure: int, gain: int, camera_index: int) -> Image:
    camera = Camera(camera_index)
    camera.set_control("Exposure", exposure)
    camera.set_control("Gain", gain)
    roi = camera.get_roi()
    roi.bins = 1
    roi.type = ImageType.rgb24
    camera.set_roi(roi)
    return camera.capture()


def _check_range(
    value: int, minimum: int = adapter.MIN_FOCUS, maximum: int = adapter.MAX_FOCUS
) -> int:
    """Check if the input value is an integer within the valid range."""
    try:
        ivalue = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value} is not a valid integer")
    if ivalue < minimum or ivalue > maximum:
        raise argparse.ArgumentTypeError(
            f"{value} is an invalid value. Must be between {minimum} and {maximum}."
        )
    return ivalue


def _valid_aperture(value: str) -> adapter.Aperture:
    try:
        return adapter.Aperture.get(value)
    except KeyError:
        raise argparse.ArgumentTypeError(
            f"{value} is not a valid aperture. Valid apertures: MAX (open), V1, ..., V10, MIN (closed)"
        )


def zwo_asi_focus():
    logging.basicConfig(level=logging.DEBUG, format="focus: %(message)s")
    parser = argparse.ArgumentParser(
        description="Change the focus and/or the aperture of the zwo-asi camera"
    )
    parser.add_argument(
        "focus",
        type=_check_range,
        help=f"desired focus. int between {adapter.MIN_FOCUS} and {adapter.MAX_FOCUS}",
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
    try:
        if args.aperture is None:
            aperture = adapter.Aperture.MAX
        else:
            aperture = args.aperture
        logger.info(f"setting focus to {args.focus} and aperture to {aperture}")
        adapter.set(args.focus, aperture)
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
    except Exception as e:
        logging.error(f"command failed with error: {e}")
        sys.exit(1)
