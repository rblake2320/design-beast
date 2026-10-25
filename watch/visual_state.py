"""CPU pixel measurements and persistent feature/text state, not action inference."""
from __future__ import annotations

import csv
import hashlib
import io
import math
from pathlib import Path
from typing import Annotated, Literal

import cv2
import numpy as np
from pydantic import Field
from PIL import Image

from .inspection import Contract

Finite = Annotated[float, Field(allow_inf_nan=False)]
Hash = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class TextElement(Contract):
    track_id: int
    text: str
    bbox: tuple[int, int, int, int]
    raw_ocr_score: Finite
    consecutive_frames: int


class MotionTrack(Contract):
    track_id: int
    before: tuple[Finite, Finite]
    after: tuple[Finite, Finite]
    forward_backward_error_px: Finite
    age_frames: int


class RegionMotion(Contract):
    bbox: tuple[int, int, int, int]
    feature_count: int
    scale: Finite
    inlier_fraction: Finite


class VisualState(Contract):
    schema_version: Literal["beast.watch.pixel-state/v1"] = "beast.watch.pixel-state/v1"
    clip_ms: Annotated[int, Field(ge=0)]
    frame_sha256: Hash
    before_sha256: Hash | None
    dimensions: tuple[int, int]
    text_elements: tuple[TextElement, ...]
    appeared_text_track_ids: tuple[int, ...]
    disappeared_text_track_ids: tuple[int, ...]
    motion_tracks: tuple[MotionTrack, ...]
    region_motion: tuple[RegionMotion, ...]
    changed_regions: tuple[tuple[int, int, int, int], ...]
    changed_pixel_fraction: Finite | None
    motion_scale: Finite | None
    affine_inlier_fraction: Finite | None
    tracking_reset: bool
    uncertainty: tuple[str, ...]
    perception_confidence: Finite | None = None
    transition_confidence: Finite | None = None
    procedure_confidence: Finite | None = None
    evidence_class: Literal["pixel_measurement_not_semantic_verdict"] = "pixel_measurement_not_semantic_verdict"


def decode_verified(path: Path, expected: str) -> np.ndarray:
    if path.stat().st_size > 64_000_000:
        raise ValueError("encoded image too large")
    pixels = path.read_bytes()
    if hashlib.sha256(pixels).hexdigest() != expected:
        raise ValueError("pixel custody mismatch")
    with Image.open(io.BytesIO(pixels)) as header:
        if header.width * header.height > 16_000_000:
            raise ValueError("oversized image dimensions")
    image = cv2.imdecode(np.frombuffer(pixels, np.uint8), cv2.IMREAD_COLOR)
    if image is None or image.shape[0] * image.shape[1] > 16_000_000:
        raise ValueError("invalid or oversized image")
    return image


def text_lines(tsv: str, width: int, height: int) -> list[tuple[str, tuple[int, int, int, int], float]]:
    if not tsv.startswith("level\tpage_num\t") or len(tsv) > 2_000_000:
        raise ValueError("invalid OCR TSV")
    groups: dict[tuple[str, ...], list[dict[str, str]]] = {}
    for row in csv.DictReader(io.StringIO(tsv), delimiter="\t"):
        if row["level"] != "5" or not row["text"].strip():
            continue
        score = float(row["conf"])
        if not math.isfinite(score) or not 0 <= score <= 100:
            raise ValueError("invalid OCR score")
        if score < 60:
            continue
        x, y, w, h = (int(row[k]) for k in ("left", "top", "width", "height"))
        if min(x, y) < 0 or min(w, h) <= 0 or x + w > width or y + h > height:
            raise ValueError("OCR box outside image")
        groups.setdefault(tuple(row[k] for k in ("page_num", "block_num", "par_num", "line_num")), []).append(row)
    result = []
    for words in groups.values():
        x = min(int(w["left"]) for w in words)
        y = min(int(w["top"]) for w in words)
        right = max(int(w["left"]) + int(w["width"]) for w in words)
        bottom = max(int(w["top"]) + int(w["height"]) for w in words)
        result.append((" ".join(w["text"] for w in words), (x, y, right - x, bottom - y),
                       min(float(w["conf"]) for w in words)))
    return result


def overlap(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    intersection = max(0, min(a[0]+a[2], b[0]+b[2])-max(a[0], b[0])) * max(0, min(a[1]+a[3], b[1]+b[3])-max(a[1], b[1]))
    return intersection / max(1, a[2]*a[3] + b[2]*b[3] - intersection)


class VisualStateTracker:
    """Feature IDs survive only validated correspondence; text IDs require text+space.

    No knowledge of Blender, source labels, known event times, or reference answers.
    """
    def __init__(self) -> None:
        cv2.setNumThreads(2)
        cv2.setRNGSeed(0)
        self.previous: np.ndarray | None = None
        self.previous_hash: str | None = None
        self.previous_ms = -1
        self.points = np.empty((0, 1, 2), dtype=np.float32)
        self.ids: list[int] = []
        self.ages: list[int] = []
        self.next_id = 0
        self.text: list[TextElement] = []
        self.next_text_id = 0

    def update(self, image: np.ndarray, stamp: int, sha: str, tsv: str) -> VisualState:
        if type(stamp) is not int or stamp <= self.previous_ms:
            raise ValueError("timestamps must strictly increase")
        if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
            raise ValueError("expected uint8 BGR pixels")
        height, width = image.shape[:2]
        if self.previous is not None and self.previous.shape != image.shape:
            raise ValueError("frame dimensions changed")
        texts: list[TextElement] = []
        used: set[int] = set()
        for content, box, score in text_lines(tsv, width, height):
            matches = [entry for entry in self.text if entry.track_id not in used and entry.text == content and overlap(entry.bbox, box) >= .5]
            old = max(matches, key=lambda e: overlap(e.bbox, box)) if matches else None
            if old is None:
                tid = self.next_text_id
                self.next_text_id += 1
            else:
                tid = old.track_id
            used.add(tid)
            texts.append(TextElement(track_id=tid, text=content, bbox=box, raw_ocr_score=score,
                                     consecutive_frames=old.consecutive_frames + 1 if old else 1))
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        tracks: list[MotionTrack] = []
        regional: list[RegionMotion] = []
        regions: list[tuple[int, int, int, int]] = []
        fraction = scale = inliers_fraction = None
        reset = self.previous is None or stamp - self.previous_ms > 1000
        reasons = ["OCR/flow scores are uncalibrated; no causal action is established",
                   "Unobserved time between samples remains uncertain"]
        survivors = np.empty((0, 1, 2), dtype=np.float32)
        ids: list[int] = []
        ages: list[int] = []
        if self.previous is not None:
            mask = (cv2.absdiff(self.previous, image).max(axis=2) > 20).astype(np.uint8)
            fraction = float(mask.mean())
            count, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
            components = sorted(stats[1:].tolist(), key=lambda s: s[4], reverse=True)
            regions = [tuple(int(v) for v in s[:4]) for s in components[:64] if s[4] >= 6]
            if count > 65:
                reasons.append("Only largest 64 connected changed regions retained")
            reset = reset or fraction > .55
            if not reset and len(self.points):
                old_gray = cv2.cvtColor(self.previous, cv2.COLOR_BGR2GRAY)
                moved, ok, _ = cv2.calcOpticalFlowPyrLK(old_gray, gray, self.points, None, winSize=(21, 21), maxLevel=3)
                if moved is not None:
                    returned, back_ok, _ = cv2.calcOpticalFlowPyrLK(gray, old_gray, moved, None, winSize=(21, 21), maxLevel=3)
                    if returned is not None:
                        errors = np.linalg.norm(returned-self.points, axis=2).reshape(-1)
                        good = (ok.reshape(-1) == 1) & (back_ok.reshape(-1) == 1) & (errors <= 1.0)
                        good &= np.isfinite(moved).all(axis=(1, 2))
                        good &= (moved[:, 0, 0] >= 0) & (moved[:, 0, 0] < width) & (moved[:, 0, 1] >= 0) & (moved[:, 0, 1] < height)
                        for index in np.flatnonzero(good):
                            tracks.append(MotionTrack(track_id=self.ids[index], before=tuple(float(v) for v in self.points[index, 0]),
                                after=tuple(float(v) for v in moved[index, 0]), forward_backward_error_px=float(errors[index]), age_frames=self.ages[index]+1))
                        survivors = moved[good]
                        ids = [track.track_id for track in tracks]
                        ages = [track.age_frames for track in tracks]
                        if len(tracks) >= 12:
                            matrix, inliers = cv2.estimateAffinePartial2D(self.points[good], survivors, method=cv2.RANSAC, ransacReprojThreshold=2.0)
                            if matrix is not None and np.isfinite(matrix).all():
                                inliers_fraction = float(inliers.mean())
                                if inliers_fraction >= .7:
                                    scale = float(math.hypot(matrix[0, 0], matrix[1, 0]))
                        # Local motion avoids interpreting static application chrome
                        # as proof that a moving viewport has not changed scale.
                        for gy in range(3):
                            for gx in range(3):
                                x, y, w, h = gx*width//3, gy*height//3, width//3, height//3
                                subset = [t for t in tracks if x <= t.before[0] < x+w and y <= t.before[1] < y+h]
                                if len(subset) < 6:
                                    continue
                                a = np.float32([t.before for t in subset])
                                b = np.float32([t.after for t in subset])
                                matrix, inliers = cv2.estimateAffinePartial2D(a, b, method=cv2.RANSAC, ransacReprojThreshold=1.5)
                                if matrix is not None and np.isfinite(matrix).all() and float(inliers.mean()) >= .7:
                                    regional.append(RegionMotion(bbox=(x, y, w, h), feature_count=len(subset),
                                        scale=float(math.hypot(matrix[0, 0], matrix[1, 0])), inlier_fraction=float(inliers.mean())))
            if not tracks:
                reasons.append("No reliable cross-frame feature correspondence")
        # Replenish tracks without giving a new point an old identity.
        selection = np.full(gray.shape, 255, dtype=np.uint8)
        for point in survivors.reshape(-1, 2):
            cv2.circle(selection, tuple(int(v) for v in point), 8, 0, -1)
        for gy in range(4):
            for gx in range(4):
                x0, y0, x1, y1 = gx*width//4, gy*height//4, (gx+1)*width//4, (gy+1)*height//4
                occupancy = sum(x0 <= p[0] < x1 and y0 <= p[1] < y1 for p in survivors.reshape(-1, 2))
                if occupancy >= 25:
                    continue
                tile_mask = np.zeros_like(selection)
                tile_mask[y0:y1, x0:x1] = selection[y0:y1, x0:x1]
                seeds = cv2.goodFeaturesToTrack(gray, maxCorners=25-int(occupancy), qualityLevel=.015, minDistance=8, mask=tile_mask)
                if seeds is not None:
                    survivors = np.concatenate((survivors, seeds))
                    ids.extend(range(self.next_id, self.next_id + len(seeds)))
                    ages.extend([1] * len(seeds))
                    self.next_id += len(seeds)
        old_text_ids = {entry.track_id for entry in self.text}
        new_text_ids = {entry.track_id for entry in texts}
        state = VisualState(clip_ms=stamp, frame_sha256=sha, before_sha256=self.previous_hash,
            dimensions=(width, height), text_elements=tuple(texts),
            appeared_text_track_ids=tuple(sorted(new_text_ids-old_text_ids)),
            disappeared_text_track_ids=tuple(sorted(old_text_ids-new_text_ids)), motion_tracks=tuple(tracks),
            region_motion=tuple(regional),
            changed_regions=tuple(regions), changed_pixel_fraction=fraction, motion_scale=scale,
            affine_inlier_fraction=inliers_fraction, tracking_reset=reset, uncertainty=tuple(reasons))
        self.previous, self.previous_hash, self.previous_ms = image.copy(), sha, stamp
        self.points, self.ids, self.ages, self.text = survivors, ids, ages, texts
        return state
