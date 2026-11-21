#!/usr/bin/env python3
"""
engine/scene_detector.py
========================
State-of-the-Art Scene & Camera Cut Detection using PySceneDetect.

Why this matters for Broadcast-Quality Clips:
- LLM transcript cuts identify speech start/end, but speakers often start speaking
  0.5s before or after a camera shot cut.
- Cutting purely on audio leaves a 0.5-second visual sliver from the previous camera shot!
- This module detects visual shot boundaries using Adaptive Content Detection and
  snaps clip boundaries to the nearest camera cut (within a safe tolerance).
"""

from pathlib import Path
from typing import List, Tuple
import subprocess

try:
    from scenedetect import detect, ContentDetector, AdaptiveDetector
    SCENEDETECT_AVAILABLE = True
except ImportError:
    SCENEDETECT_AVAILABLE = False


def detect_camera_cuts(
    video_path: Path,
    adaptive_threshold: float = 3.0,
    min_scene_len_sec: float = 0.8,
) -> List[float]:
    """
    Run PySceneDetect over the video file to find exact camera cut timestamps in seconds.
    Uses AdaptiveDetector (SOTA for both hard cuts and moving camera pans).
    """
    if not SCENEDETECT_AVAILABLE:
        return []

    try:
        # Detect scenes
        scene_list = detect(
            str(video_path),
            AdaptiveDetector(adaptive_threshold=adaptive_threshold, min_scene_len=int(min_scene_len_sec * 30)),
        )
        cut_timestamps = []
        for scene in scene_list:
            start_sec = scene[0].get_seconds()
            cut_timestamps.append(round(start_sec, 3))
        return cut_timestamps
    except Exception as e:
        print(f"Warning: Scene detection failed: {e}")
        return []


def snap_to_camera_cut(
    target_sec: float,
    cut_timestamps: List[float],
    max_tolerance_sec: float = 1.2,
) -> float:
    """
    If there is a camera cut within max_tolerance_sec of target_sec, snap to it.
    Otherwise, return target_sec unchanged.
    """
    if not cut_timestamps:
        return target_sec

    closest_cut = min(cut_timestamps, key=lambda c: abs(c - target_sec))
    if abs(closest_cut - target_sec) <= max_tolerance_sec:
        return closest_cut

    return target_sec


def refine_clip_boundaries_with_scenes(
    start_sec: float,
    end_sec: float,
    video_path: Path,
    tolerance_sec: float = 1.2,
) -> Tuple[float, float]:
    """
    Refine clip start/end using detected camera cuts.
    Prevents visual shot slivers at the beginning and end of clips.
    """
    cuts = detect_camera_cuts(video_path)
    if not cuts:
        return start_sec, end_sec

    refined_start = snap_to_camera_cut(start_sec, cuts, max_tolerance_sec=tolerance_sec)
    refined_end = snap_to_camera_cut(end_sec, cuts, max_tolerance_sec=tolerance_sec)

    return refined_start, refined_end
