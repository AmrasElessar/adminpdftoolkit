"""Photo / scan clean-up for images that become PDF pages.

* ``auto_orient``  — honour the camera's EXIF orientation.
* ``find_document`` + ``warp_document`` — locate a sheet of paper in a photo
  (largest convex quadrilateral) and flatten its perspective.
* ``detect_skew`` + ``rotate`` — straighten slightly tilted scans by
  maximising the variance of the horizontal ink profile (text lines line up).
* ``enhance`` — even out lighting / shadows, grayscale or black & white.

All functions take and return Pillow images; OpenCV does the heavy lifting.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
from PIL import Image, ImageOps

Enhance = Literal["none", "auto", "gray", "bw"]

# Work on a downscaled copy for analysis: fast and robust to noise.
ANALYSIS_EDGE = 1000
MAX_SKEW_DEGREES = 15.0


def auto_orient(img: Image.Image) -> Image.Image:
    return ImageOps.exif_transpose(img) or img


def _to_rgb(img: Image.Image) -> Image.Image:
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        rgba = img.convert("RGBA")
        bg.paste(rgba, mask=rgba.getchannel("A"))
        return bg
    return img.convert("RGB") if img.mode not in ("RGB", "L") else img


def _analysis_gray(img: Image.Image) -> tuple[np.ndarray, float]:
    """Grayscale uint8 array scaled so the long edge is ANALYSIS_EDGE."""
    scale = min(1.0, ANALYSIS_EDGE / max(img.size))
    small = img if scale == 1.0 else img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))))
    return np.asarray(small.convert("L")), scale


def find_document(img: Image.Image) -> np.ndarray | None:
    """Corners (tl, tr, br, bl) of the sheet in a photo, in full-size pixels,
    or None when no clear page outline exists (e.g. a flat scan)."""
    import cv2

    gray, scale = _analysis_gray(img)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 50, 150)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=2)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    area_total = gray.shape[0] * gray.shape[1]
    for c in sorted(contours, key=cv2.contourArea, reverse=True)[:8]:
        area = cv2.contourArea(c)
        if area < 0.25 * area_total:
            break
        approx = cv2.approxPolyDP(c, 0.02 * cv2.arcLength(c, True), True)
        if len(approx) == 4 and cv2.isContourConvex(approx):
            if area > 0.97 * area_total:
                return None  # the "outline" is just the image border
            pts = approx.reshape(4, 2).astype("float32") / scale
            # Pull corners 0.8 % towards the centre: edge detection sits on
            # the paper border, and the desk would otherwise show as a seam.
            centre = pts.mean(axis=0)
            pts = centre + (pts - centre) * 0.984
            return _order_corners(pts.astype("float32"))
    return None


def _order_corners(pts: np.ndarray) -> np.ndarray:
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).ravel()
    return np.array([pts[np.argmin(s)], pts[np.argmin(d)], pts[np.argmax(s)], pts[np.argmax(d)]], dtype="float32")


def page_aspect(corners: np.ndarray, size: tuple[int, int]) -> float | None:
    """Real width/height ratio of the photographed sheet.

    Recovers the camera focal length from the quadrilateral's vanishing
    geometry (Zhang & He, "Whiteboard scanning and image enhancement",
    2007) so foreshortening doesn't stretch the result. None if degenerate.
    """
    tl, tr, br, bl = corners
    u0, v0 = size[0] / 2, size[1] / 2

    def h(p: np.ndarray) -> np.ndarray:
        return np.array([p[0] - u0, p[1] - v0, 1.0])

    m1, m2, m3, m4 = h(tl), h(tr), h(bl), h(br)
    d2 = np.dot(np.cross(m2, m4), m3)
    d3 = np.dot(np.cross(m3, m4), m2)
    if abs(d2) < 1e-9 or abs(d3) < 1e-9:
        return None
    k2 = np.dot(np.cross(m1, m4), m3) / d2
    k3 = np.dot(np.cross(m1, m4), m2) / d3
    n2 = k2 * m2 - m1
    n3 = k3 * m3 - m1
    denom = n2[2] * n3[2]
    f2 = -(n2[0] * n3[0] + n2[1] * n3[1]) / denom if abs(denom) > 1e-12 else -1.0
    if f2 > 0:
        a_inv = np.diag([1 / np.sqrt(f2), 1 / np.sqrt(f2), 1.0])
        num = n2 @ a_inv.T @ a_inv @ n2
        den = n3 @ a_inv.T @ a_inv @ n3
    else:  # near-orthographic view: plain side lengths
        num = n2[0] ** 2 + n2[1] ** 2
        den = n3[0] ** 2 + n3[1] ** 2
    if den <= 0 or num <= 0:
        return None
    ratio = float(np.sqrt(num / den))
    return ratio if 0.2 < ratio < 5 else None


def warp_document(img: Image.Image, corners: np.ndarray) -> Image.Image:
    import cv2

    tl, tr, br, bl = corners
    width = int(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)))
    height = int(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl)))
    aspect = page_aspect(corners, img.size)
    if aspect is not None:
        height = int(width / aspect)
    if width < 50 or height < 50:
        return img
    dst = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype="float32")
    m = cv2.getPerspectiveTransform(corners, dst)
    arr = np.asarray(_to_rgb(img))
    out = cv2.warpPerspective(arr, m, (width, height), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return Image.fromarray(out)


def detect_skew(img: Image.Image) -> float:
    """Clockwise tilt in degrees to undo (positive = rotate counter-clockwise
    to fix). 0.0 when the page has too little ink to judge."""
    import cv2

    gray, _ = _analysis_gray(img)
    _, ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    if ink.mean() < 1.0 or ink.mean() > 128:  # blank page or a photo, not text
        return 0.0
    h, w = ink.shape
    center = (w / 2, h / 2)

    def score(angle: float) -> float:
        m = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(ink, m, (w, h), flags=cv2.INTER_NEAREST)
        profile = rotated.sum(axis=1, dtype=np.float64)
        return float(np.var(profile))

    coarse = max(np.arange(-MAX_SKEW_DEGREES, MAX_SKEW_DEGREES + 0.01, 1.0), key=score)
    fine = max(np.arange(coarse - 1.0, coarse + 1.01, 0.1), key=score)
    return round(float(fine), 2)


def rotate(img: Image.Image, angle: float) -> Image.Image:
    """Rotate counter-clockwise by ``angle`` degrees, filling with white."""
    if abs(angle) < 0.05:
        return img
    rgb = _to_rgb(img)
    fill = 255 if rgb.mode == "L" else (255, 255, 255)
    return rgb.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True, fillcolor=fill)


def enhance(img: Image.Image, mode: Enhance) -> Image.Image:
    if mode == "none":
        return img
    import cv2

    gray = np.asarray(img.convert("L"))
    if mode == "gray":
        return ImageOps.autocontrast(Image.fromarray(gray), cutoff=1)
    # Flatten uneven lighting and shadows: divide by a heavy blur of the page.
    k = max(15, (min(gray.shape) // 20) | 1)
    background = cv2.medianBlur(gray, k if k % 2 else k + 1)
    flat = cv2.divide(gray, background, scale=255)
    if mode == "bw":
        bw = cv2.adaptiveThreshold(flat, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10)
        return Image.fromarray(bw).convert("1")
    # "auto": keep colour, apply the lighting correction as a gain map.
    rgb = np.asarray(_to_rgb(img).convert("RGB")).astype(np.float32)
    gain = (flat.astype(np.float32) + 1) / (gray.astype(np.float32) + 1)
    out = np.clip(rgb * gain[..., None], 0, 255).astype(np.uint8)
    return ImageOps.autocontrast(Image.fromarray(out), cutoff=0.5)
