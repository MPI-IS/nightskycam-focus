from dataclasses import dataclass
from typing import Dict, Tuple

import cv2
import numpy as np
from scipy.optimize import curve_fit


@dataclass
class Gaussian2D:
    amplitude: float
    mean: Tuple[float, float]
    std: Tuple[float, float]
    theta: float = 0.0


def _compute_gaussian2D(data, amplitude, xo, yo, sigma_x, sigma_y, theta, offset):
    X, Y = data
    xo = float(xo)
    yo = float(yo)
    a = (np.cos(theta) ** 2) / (2 * sigma_x**2) + (np.sin(theta) ** 2) / (
        2 * sigma_y**2
    )
    b = -(np.sin(2 * theta)) / (4 * sigma_x**2) + (np.sin(2 * theta)) / (4 * sigma_y**2)
    c = (np.sin(theta) ** 2) / (2 * sigma_x**2) + (np.cos(theta) ** 2) / (
        2 * sigma_y**2
    )
    g = offset + amplitude * np.exp(
        -(a * ((X - xo) ** 2) + 2 * b * (X - xo) * (Y - yo) + c * ((Y - yo) ** 2))
    )
    return g.ravel()


def fit_gaussian2d(image: np.ndarray) -> Gaussian2D:

    h, w = image.shape
    data = image.ravel()
    x = np.linspace(0, w, w)
    y = np.linspace(0, h, h)
    x, y = np.meshgrid(x, y)

    threshold = 0.10

    max_val = np.max(image)
    min_val = np.min(image)
    image0 = image * (image > (max_val - min_val) * threshold)
    image_sum = image0.sum()
    mean_gauss_x = (x * image0).sum() / image_sum
    mean_gauss_y = (y * image0).sum() / image_sum
    sigma_gauss_x = np.sqrt((image0 * (x - mean_gauss_x) ** 2).sum() / image_sum)
    sigma_gauss_y = np.sqrt((image0 * (y - mean_gauss_y) ** 2).sum() / image_sum)

    initial_guess = (
        max_val - min_val,
        mean_gauss_x,
        mean_gauss_y,
        sigma_gauss_x,
        sigma_gauss_y,
        0,
        np.min(image),
    )

    try:
        popt, _ = curve_fit(_compute_gaussian2D, (x, y), data, p0=initial_guess)
    except RuntimeError as e:
        popt = initial_guess

    fitted_params = Gaussian2D(
        amplitude=popt[0],
        mean=(popt[1], popt[2]),
        std=(popt[3], popt[4]),
        theta=popt[5],
    )

    return fitted_params


def gaussian2d_score(image: np.ndarray) -> float:
    gaussian: Gaussian2D = fit_gaussian2d(image)
    mean_std = (abs(gaussian.std[0]) + abs(gaussian.std[1])) / 2.0
    return mean_std


def laplacian_score(image):
    laplacian = cv2.Laplacian(image, cv2.CV_64F)
    variance = laplacian.var()
    return variance


def brenner_score(image):
    shifted_image = np.roll(image, -1, axis=0)
    differences = image - shifted_image
    brenner_score = np.sum(differences[:-1, :] ** 2)
    return brenner_score


def sobel_score(image):
    sobel_x = cv2.Sobel(image, cv2.CV_64F, 1, 0, ksize=3)
    sobel_y = cv2.Sobel(image, cv2.CV_64F, 0, 1, ksize=3)
    gradient_magnitude = np.sqrt(sobel_x**2 + sobel_y**2)
    focus_measure = np.mean(gradient_magnitude)
    return focus_measure


def _rayleigh(z, w0, z0, zR):
    return w0 * np.sqrt(1 + ((z - z0) / zR) ** 2)


def _fit_rayleigh(focus_score: Dict[int, float]) -> list[float]:
    focus_range = np.array(list([float(f) for f in sorted(focus_score.keys())]))
    scores = np.array([focus_score[f] for f in focus_range])
    popt, _ = curve_fit(
        _rayleigh,
        focus_range,
        scores,
        p0=(scores.min(), focus_range.mean(), 50),
    )
    return list(popt)


def min_rayleigh(focus_score: Dict[int, float]) -> int:
    rayleigh = _fit_rayleigh(focus_score)
    return int(rayleigh[1] + 0.5)
