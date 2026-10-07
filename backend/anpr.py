"""
ANPR (Automatic Number Plate Recognition) for the mall parking system.

Pipeline (from your notebook):
    image bytes -> YOLO segmentation -> 4-point quad -> perspective warp
    -> PaddleOCR TextRecognition -> cleaned plate string

IMPORTANT: the models are loaded ONCE, when this module is first imported
(i.e. when the server starts). detect_plate() only runs prediction, so each
Entry/Exit click is fast.

Put your weights file next to this file:  backend/best_segment.pt
"""

import re
import threading
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO
from paddleocr import TextRecognition

# ---------------------------------------------------------------- settings
WEIGHTS = Path(__file__).parent / "best_segment.pt"
CONF_THRESHOLD = 0.25      # YOLO detection confidence
MIN_OCR_SCORE = 0.50       # ignore OCR results less sure than this (tune it)
MIN_PLATE_LEN = 6          # shortest string we accept as a plate

# ------------------------------------------- load models ONCE (at startup)
print("[ANPR] Loading models...")
_yolo = YOLO(str(WEIGHTS))
_recognizer = TextRecognition(model_name="PP-OCRv5_server_rec")

# Two gates clicking at the same moment should not run the models at the
# same time, so we take turns.
_lock = threading.Lock()


def _warm_up():
    """Run one dummy prediction so the FIRST real click isn't slow."""
    try:
        dummy = np.zeros((320, 320, 3), dtype=np.uint8)
        _yolo.predict(source=dummy, conf=CONF_THRESHOLD, verbose=False)
        _recognizer.predict(input=np.zeros((48, 160, 3), dtype=np.uint8), batch_size=1)
    except Exception as e:
        print(f"[ANPR] Warm-up skipped: {e}")


_warm_up()
print("[ANPR] Models ready.")


# ------------------------------------------------------- helper functions
def simplify_to_quad(mask_points):
    """Reduce a mask contour (many points) down to a 4-point quadrilateral."""
    pts = np.array(mask_points, dtype=np.float32).reshape((-1, 1, 2))
    peri = cv2.arcLength(pts, True)

    for factor in np.arange(0.01, 0.2, 0.005):
        approx = cv2.approxPolyDP(pts, factor * peri, True)
        if len(approx) == 4:
            return approx.reshape(4, 2)

    rect = cv2.minAreaRect(pts)
    return cv2.boxPoints(rect)


def order_points(pts):
    """Order 4 points as: top-left, top-right, bottom-right, bottom-left."""
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1)
    rect[0] = pts[np.argmin(s)]      # top-left
    rect[2] = pts[np.argmax(s)]      # bottom-right
    rect[1] = pts[np.argmin(diff)]   # top-right
    rect[3] = pts[np.argmax(diff)]   # bottom-left
    return rect


def warp_quad(img, quad):
    """Perspective-warp the quadrilateral region into a straight rectangle."""
    rect = order_points(quad.astype(np.float32))
    (tl, tr, br, bl) = rect

    max_w = max(int(np.linalg.norm(br - bl)), int(np.linalg.norm(tr - tl)))
    max_h = max(int(np.linalg.norm(tr - br)), int(np.linalg.norm(tl - bl)))
    if max_w < 2 or max_h < 2:
        return None

    dst = np.array(
        [[0, 0], [max_w - 1, 0], [max_w - 1, max_h - 1], [0, max_h - 1]],
        dtype=np.float32,
    )
    M = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(img, M, (max_w, max_h))


def clean_plate_text(text: str) -> str:
    """Keep only A-Z and 0-9, uppercase."""
    return re.sub(r"[^A-Za-z0-9]", "", text).upper()


# ------------------------------------------------- the function main.py calls
def detect_plate(image_bytes: bytes) -> str | None:
    """
    Takes raw image bytes (one frame from the gate camera) and returns the
    plate number as a string like "OD02AB1234", or None if nothing was read.
    """
    # bytes -> OpenCV image (BGR), entirely in memory
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return None

    with _lock:
        # 1) find the plate(s) in the frame
        results = _yolo.predict(source=img, conf=CONF_THRESHOLD, verbose=False)
        r = results[0]
        if r.masks is None or len(r.masks) == 0:
            return None

        # 2) try the most confident detection first
        order = sorted(range(len(r.masks.xy)),
                       key=lambda i: float(r.boxes[i].conf[0]), reverse=True)

        for i in order:
            quad = simplify_to_quad(r.masks.xy[i])
            cropped = warp_quad(img.copy(), quad)
            if cropped is None:
                continue

            # 3) read the text from the straightened crop
            ocr_out = _recognizer.predict(input=cropped, batch_size=1)
            for res in ocr_out or []:
                data = res.json["res"]
                text = clean_plate_text(data.get("rec_text", ""))
                score = float(data.get("rec_score", 0))
                if len(text) >= MIN_PLATE_LEN and score >= MIN_OCR_SCORE:
                    return text

    return None