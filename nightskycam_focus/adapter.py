import logging
import time
from contextlib import contextmanager
from enum import Enum
from warnings import warn

import spidev

try:
    import RPi.GPIO as GPIO

    _GPIO_IMPORTED = True
except (RuntimeError, ModuleNotFoundError):
    _GPIO_IMPORTED = False

logger = logging.getLogger(__name__)

MIN_FOCUS = 1
MAX_FOCUS = 3071
SS_PIN = 5
RESET_PIN = 6
MAX_SPEED_HZ = 1000000
SLEEP = 0.1
MIDDLE_SLEEP = 2.0
LONG_SLEEP = 5.0


class _CommandType(Enum):
    OPEN = "O"
    FOCUS = "F"
    APERTURE = "A"


class Aperture(Enum):
    MAX = 441
    V0 = 441
    V1 = 512
    V2 = 646
    V3 = 706
    V4 = 857
    V5 = 926
    V6 = 1110
    V7 = 1159
    V8 = 1271
    V9 = 1347
    V10 = 1468
    V11 = 2303
    MIN = 2303

    @classmethod
    def is_valid(cls, aperture: str) -> bool:
        return aperture in cls.__members__

    @classmethod
    def get(cls, aperture: str) -> "Aperture":
        return cls.__members__[aperture]


def _crc8_custom(data):
    crc = 0x00
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ 0x05) & 0xFF
            else:
                crc <<= 1
            crc &= 0xFF

    return crc


@contextmanager
def _closing(spi: spidev.SpiDev):
    try:
        yield
    finally:
        logger.debug("closing adapter")
        spi.close()
        GPIO.cleanup()
        logger.debug("adapter closed")


def _send_command(command_type: _CommandType, value: int):

    value1, value2 = divmod(value, 256)

    logger.debug("opening adapter")
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(SS_PIN, GPIO.OUT)
    GPIO.output(SS_PIN, GPIO.HIGH)
    spi = spidev.SpiDev()
    spi.open(0, 0)
    logger.debug("adapter opened")

    spi.max_speed_hz = MAX_SPEED_HZ
    command = ord(command_type.value)
    data_to_send1 = [command, value1, value2]
    crc1 = _crc8_custom(data_to_send1)
    data_to_send1.append(crc1)

    with _closing(spi):

        logger.debug(f"setting pin {SS_PIN} to low")
        GPIO.output(SS_PIN, GPIO.LOW)

        resp = spi.xfer3(data_to_send1)
        logger.debug(f"sent: {data_to_send1}, received: {resp}")

        if command_type in (_CommandType.FOCUS, _CommandType.APERTURE):
            command_r = 0x00
            value1_r = 0x00
            value2_r = 0x00
            time.sleep(1)
            data_to_send2 = [command_r, value1_r, value2_r]
            crc2 = _crc8_custom(data_to_send2)
            data_to_send2.append(crc2)
            resp = spi.xfer3(data_to_send2)
            logger.debug(f"sent: {data_to_send2}, received: {resp}")

        if command_type == _CommandType.OPEN:
            time.sleep(LONG_SLEEP)

        logger.debug(f"setting pin {SS_PIN} to high")
        GPIO.output(SS_PIN, GPIO.HIGH)


def _reset():
    logger.debug("resetting adapter")
    GPIO.setmode(GPIO.BCM)
    logger.debug(f"setting pin {RESET_PIN} to out")
    GPIO.setup(RESET_PIN, GPIO.OUT)
    try:
        logger.debug(f"setting pin {RESET_PIN} to low")
        GPIO.output(RESET_PIN, GPIO.LOW)
        time.sleep(SLEEP)
    finally:
        logger.debug("gpio cleanup")
        GPIO.cleanup()
    logger.debug("adapter reset")


def set(focus: int, aperture: Aperture):
    if not _GPIO_IMPORTED:
        raise RuntimeError("GPIO module can be used only on Raspberry Pi")
    if focus < MIN_FOCUS or focus > MAX_FOCUS:
        raise ValueError(
            f"focus should be between {MIN_FOCUS} and {MAX_FOCUS} ({focus} invalid)"
        )
    _reset()
    time.sleep(MIDDLE_SLEEP)
    _send_command(_CommandType.OPEN, 0)
    time.sleep(MIDDLE_SLEEP)
    _send_command(_CommandType.APERTURE, aperture.value)
    time.sleep(MIDDLE_SLEEP)
    _send_command(_CommandType.FOCUS, focus)
    time.sleep(MIDDLE_SLEEP)
    _reset()
    logger.info(f"set focus to {focus} and aperture to {aperture}")


def set_focus(value: int):
    set(value, Aperture.MAX)


@contextmanager
def adapter():
    warn(
        'The focus/aperture context manager "adapter" is deprecated. Call "set" or "set_focus" directly.'
    )
    yield
