import logging
import time
from contextlib import contextmanager
from enum import Enum
from typing import Generator, List, NewType

try:
    import RPi.GPIO as GPIO

    _GPIO_IMPORTED = True
except RuntimeError:
    _GPIO_IMPORTED = False

import spidev

MIN_FOCUS = 1
MAX_FOCUS = 3071


class _Wait(Enum):
    VERY_SHORT = 0.5
    SHORT = 0.6
    REGULAR = 1.0
    LONG = 5.0


class CommandType(Enum):
    OPEN = "O"
    IDLE = "I"
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


PIN = NewType("PIN", int)
SS_PIN = PIN(5)
RESET_PIN = PIN(6)

_SPI_MAX_HZ: int = 1000000


@contextmanager
def _gpio() -> Generator[spidev.SpiDev, None, None]:
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(SS_PIN, GPIO.OUT)
    GPIO.output(SS_PIN, GPIO.HIGH)
    spi = spidev.SpiDev()
    spi.open(0, 0)
    spi.max_speed_hz = _SPI_MAX_HZ
    try:
        yield spi
    except KeyboardInterrupt:
        spi.close()
        GPIO.cleanup()
    else:
        GPIO.output(SS_PIN, GPIO.HIGH)
        spi.close()
        GPIO.cleanup()


def _send_spi_data(spi: spidev.SpiDev, data: List[int]) -> List[int]:
    return spi.xfer3(data)


def _crc8_custom(data: List[int]) -> int:
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


def _prepare_message(command: int, v1: int, v2: int) -> List[int]:
    d = [command, v1, v2]
    crc = _crc8_custom(d)
    d.append(crc)
    return d


_RESET_MESSAGE = _prepare_message(0x00, 0x00, 0x00)
_ERROR_RESET = (2, 2, 2, 2)


def _spi_send(
    spi: spidev.SpiDev, command_type: CommandType, value: int
) -> None:
    logging.debug(f"command {command_type}: {value}")
    v1, v2 = divmod(value, 256)
    command = ord(command_type.value)
    message = _prepare_message(command, v1, v2)
    GPIO.output(SS_PIN, GPIO.LOW)
    logging.debug(f"command message: {message}")
    resp = spi.xfer3(message)
    logging.debug(f"response: {resp}")


def _send_command(
    command_type: CommandType, value: int, max_attempts: int = 10
) -> None:
    attempt = 1
    while attempt < max_attempts:
        with _gpio() as spi:
            _spi_send(spi, command_type, value)
            if command_type in (CommandType.FOCUS, CommandType.APERTURE):
                time.sleep(_Wait.SHORT.value)
                reset_resp = spi.xfer3(_RESET_MESSAGE)
                logging.debug(f"reset response: {reset_resp}")
                if reset_resp != _ERROR_RESET:
                    return
            elif command_type == CommandType.OPEN:
                time.sleep(_Wait.LONG.value)
                return
            elif command_type == CommandType.IDLE:
                return
            attempt += 1

    error_message = f"failed to run command: '{command_type.value}: {value}'"
    raise RuntimeError(error_message)


def reset_adapter() -> None:
    logging.debug("resetting adapter")
    logging.debug("GPIO set mode")
    GPIO.setmode(GPIO.BCM)
    logging.debug("GPIO setup")
    GPIO.setup(RESET_PIN, GPIO.OUT)
    try:
        logging.debug("GPIO output")
        GPIO.output(RESET_PIN, GPIO.LOW)
        time.sleep(_Wait.VERY_SHORT.value)
    finally:
        logging.debug("GPIO cleanup")
        GPIO.cleanup()
    logging.debug("adapter reset")
    time.sleep(_Wait.SHORT.value)


def init_adapter() -> None:
    if not _GPIO_IMPORTED:
        raise RuntimeError("GPIO module can be used only on Raspberry Pi")
    reset_adapter()
    logging.debug("adapter: sending open command")
    _send_command(CommandType.OPEN, 0)
    logging.debug("adapter: open command sent")


def idle_adapter() -> None:
    _send_command(CommandType.IDLE, 0)


@contextmanager
def adapter():
    init_adapter()
    try:
        yield
        error = None
    except Exception as e:
        error = e
    finally:
        logging.debug("adapter: sending idle command")
        idle_adapter()
        logging.debug("adapter: idle command sent")
    if error:
        logging.error(error)
        raise error


def set_focus(target_value: int) -> None:
    _send_command(CommandType.FOCUS, target_value)


def set_aperture(target_value: Aperture) -> None:
    value: int = target_value.value
    _send_command(CommandType.APERTURE, value)
