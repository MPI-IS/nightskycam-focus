from typing import Optional
from typing import Tuple
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


class CommandType(Enum():
    OPEN="O"
    IDLE="I"
    FOCUS="F"
    APERTURE="A"


class Aperture(Enum):
    MAX=441
    V0=441
    V1=512
    V2=646
    V3=706
    V4=857
    V5=926
    V6=1110
    V7=1159
    V8=1271
    V9=1347
    V10=1468
    V11=2303
    MIN=2303

    @ classmethod
    def is_valid(cls, aperture: str) -> bool:
        return aperture in cls.__members__

    @ classmethod
    def get(cls, aperture: str) -> "Aperture":
        return cls.__members__[aperture]


PIN=NewType("PIN", int)
SS_PIN=PIN(5)
RESET_PIN=PIN(6)
_SPI_MAX_HZ: int=1000000
_ERROR_RESET=(2, 2, 2, 2)
_ERROR_RESPONSE=(0, 0, 0, 0)
_ERROR_RESPONSES=(_ERROR_RESET, _ERROR_RESPONSE)


@ contextmanager
def _gpio() -> Generator[spidev.SpiDev, None, None]:
    logging.debug("opening gpio / spidev")
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(SS_PIN, GPIO.OUT)
        # Keep SS high when idle, align with reference implementation
        GPIO.output(SS_PIN, GPIO.HIGH)
        spi=spidev.SpiDev()
        spi.open(0, 0)
        spi.max_speed_hz=_SPI_MAX_HZ
        yield spi
    except Exception as e:
        logging.error(f"gpio / spidev error: {e}")
        try:
            GPIO.output(SS_PIN, GPIO.HIGH)
        except:
            pass
        spi.close()
        GPIO.cleanup()
        raise e
    else:
        logging.debug("closing gpio / spidev")
        GPIO.output(SS_PIN, GPIO.HIGH)
        spi.close()
        GPIO.cleanup()


def _crc8_custom(data: List[int]) -> int:
    crc=0x00
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc=((crc << 1) ^ 0x05) & 0xFF
            else:
                crc <<= 1
        crc &= 0xFF
    return crc


def _prepare_message(command: int, v1: int, v2: int) -> List[int]:
    d=[command, v1, v2]
    crc=_crc8_custom(d)
    d.append(crc)
    return d


_RESET_MESSAGE=_prepare_message(0x00, 0x00, 0x00)


def _spi_send(
    command_type: CommandType,
    value: int,
    sleep: Optional[_Wait],
    reset: bool,
) -> Tuple[int, int, int, int]:

    logging.debug(f"command {command_type}: {value}")
    v1, v2=divmod(value, 256)
    command=ord(command_type.value)
    message=_prepare_message(command, v1, v2)

    logging.debug(f"command message: {message}")
    with _gpio() as spi:
        # Assert SS low just for the transfer
        GPIO.output(SS_PIN, GPIO.LOW)
        response=tuple(spi.xfer3(message))
        GPIO.output(SS_PIN, GPIO.HIGH)
        logging.debug(f"response: {response}")
        if response in _ERROR_RESPONSES:
            raise RuntimeError(f"received invalid response: {response}")
        if reset:
            # Align with reference: wait about 1.5 seconds before reset transfer
            time.sleep(1.5)
            GPIO.output(SS_PIN, GPIO.LOW)
            reset_resp=tuple(spi.xfer3(_RESET_MESSAGE))
            GPIO.output(SS_PIN, GPIO.HIGH)
            if reset_resp in _ERROR_RESPONSES:
                raise RuntimeError(f"received invalid response: {reset_resp}")
        if sleep:
            time.sleep(sleep.value)

    return response


def _aperture_command(value: int):
    _spi_send(CommandType.APERTURE, value, None, True)


def _focus_command(value: int):
    _spi_send(CommandType.FOCUS, value, None, True)


def _open_command():
    _spi_send(CommandType.OPEN, 0, _Wait.LONG, False)


def _idle_command():
    _spi_send(CommandType.IDLE, 0, None, False)


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


@ contextmanager
def adapter():
    if not _GPIO_IMPORTED:
        raise RuntimeError("GPIO module can be used only on Raspberry Pi")
    # Do not send OPEN on entry by default; align with reference minimal program
    try:
        yield
        error=None
    except Exception as e:
        error=e
    finally:
        logging.debug("adapter: sending idle command")
        _idle_command()
        logging.debug("adapter: idle command sent")
    if error:
        logging.error(error)
        raise error


def set_focus(value: int) -> None:
    if value < MIN_FOCUS or value > MAX_FOCUS:
        raise ValueError(
            f"focus should be between {MIN_FOCUS} and {MAX_FOCUS} ({value} invalid)"
        )
    _focus_command(value)


def set_aperture(value: Aperture) -> None:
    value_: int=value.value
    _aperture_command(value_)
