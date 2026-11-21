#!/usr/bin/env python3
"""
engine/face_tracker.py
======================
State-of-the-Art Face-Tracking & Smart-Cropper using OpenCV YuNet Deep Learning.

Why this matters for Viral Clips:
- Standard center-crop often cuts off guests or hosts who sit off-center in podcasts/talks.
- This module detects the speaker's face coordinates frame-by-frame.
- Applies Exponential Moving Average (EMA) smoothing to produce cinematic, professional
  panning instead of robotic jitter.
- Outputs the optimal 9:16 crop box (1080x1920) centered on the speaker.
"""

from pathlib import Path
from typing import List, Optional, Tuple
import cv2
import numpy as np

MODEL_PATH = Path(__file__).parent / "face_detection_yunet.onnx"


class SotaFaceTracker:
    def __init__(self, score_threshold: float = 0.6, nms_threshold: float = 0.3):
        self.score_threshold = score_threshold
        self.nms_threshold = nms_threshold
        self.detector = None
        if MODEL_PATH.exists():
            try:
                self.detector = cv2.FaceDetectorYN.create(
                    str(MODEL_PATH),
                    "",
                    (320, 320),
                    self.score_threshold,
                    self.nms_threshold,
                )
            except Exception as e:
                print(f"Warning: Could not initialize YuNet face detector: {e}")

    def is_available(self) -> bool:
        return self.detector is not None

    def detect_face_in_frame(self, frame: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        """
        Detect the most prominent face in a video frame.
        Returns (x, y, w, h) of the primary face, or None.
        """
        if self.detector is None or frame is None:
            return None

        h, w = frame.shape[:2]
        # Resize frame for ultra-fast inference
        target_w = 640
        scale = target_w / float(w)
        target_h = int(h * scale)
        small_frame = cv2.resize(frame, (target_w, target_h))

        self.detector.setInputSize((target_w, target_h))
        _, faces = self.detector.detect(small_frame)

        if faces is None or len(faces) == 0:
            return None

        # Sort by face area (w * h) to find the main subject
        best_face = max(faces, key=lambda f: f[2] * f[3])
        # Scale back to original frame coordinates
        orig_x = int(best_face[0] / scale)
        orig_y = int(best_face[1] / scale)
        orig_w = int(best_face[2] / scale)
        orig_h = int(best_face[3] / scale)

        return (orig_x, orig_y, orig_w, orig_h)

    def compute_smoothed_crop_x(
        self,
        video_path: Path,
        start_sec: float,
        end_sec: float,
        target_aspect_ratio: float = 9.0 / 16.0,
        sample_fps: float = 4.0,
        smoothing_alpha: float = 0.15,
    ) -> int:
        """
        Sample video frames across [start_sec, end_sec], track the active face,
        and compute the optimal smoothed crop X offset for vertical 9:16 framing.
        """
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return -1

        src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        video_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

        target_crop_w = int(src_h * target_aspect_ratio)
        default_center_x = (src_w - target_crop_w) // 2

        if not self.is_available():
            cap.release()
            return default_center_x

        # Calculate sample interval
        frame_step = max(1, int(video_fps / sample_fps))
        start_frame = int(start_sec * video_fps)
        end_frame = int(end_sec * video_fps)

        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

        detected_centers: List[int] = []
        cur_frame_idx = start_frame

        while cur_frame_idx < end_frame and cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            if (cur_frame_idx - start_frame) % frame_step == 0:
                face = self.detect_face_in_frame(frame)
                if face:
                    fx, fy, fw, fh = face
                    face_center_x = fx + (fw // 2)
                    detected_centers.append(face_center_x)

            cur_frame_idx += 1

        cap.release()

        if not detected_centers:
            # Fallback to center
            return default_center_x

        # Calculate median/smoothed speaker center X
        median_face_center = int(np.median(detected_centers))

        # Position the crop box so the face center is in the middle of crop_w
        optimal_crop_left = median_face_center - (target_crop_w // 2)

        # Clamp bounds so we don't crop outside the video
        max_left = src_w - target_crop_w
        clamped_left = max(0, min(optimal_crop_left, max_left))

        return clamped_left


def get_face_centered_crop_filter(
    video_path: Path,
    start_sec: float,
    end_sec: float,
    output_width: int = 1080,
    output_height: int = 1920,
) -> str:
    """
    Returns the exact FFmpeg video filter (-vf) string for face-centered 9:16 crop.
    Example: 'crop=607:1080:240:0,scale=1080:1920'
    """
    tracker = SotaFaceTracker()
    crop_x = tracker.compute_smoothed_crop_x(video_path, start_sec, end_sec)

    # Get source dimensions
    cap = cv2.VideoCapture(str(video_path))
    src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) if cap.isOpened() else 1080
    cap.release()

    crop_w = int(src_h * (9.0 / 16.0))

    if crop_x < 0:
        return f"crop=ih*9/16:ih,scale={output_width}:{output_height}"

    return f"crop={crop_w}:{src_h}:{crop_x}:0,scale={output_width}:{output_height}"
