#!/usr/bin/env python3
"""
engine/audio_beat_sync.py
=========================
Audio Intelligence & Transient Detection Engine.
Extracts audio energy envelope, detects speech emphasis, volume peaks,
excitement spikes, and transient onsets natively using FFmpeg + NumPy.
Zero extra dependencies (no heavy librosa/scipy required).
"""

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple
import numpy as np


@dataclass
class AudioEnergyProfile:
    duration: float
    sample_rate: int
    rms_envelope: np.ndarray       # 50ms hop RMS values
    time_points: np.ndarray        # Timestamp corresponding to each RMS value
    mean_energy: float
    max_energy: float
    energy_spikes: List[float]     # Timestamps of significant volume / excitement spikes
    transient_onsets: List[float]  # Timestamps of sharp attack transients
    quiet_valleys: List[float]     # Timestamps of natural speech pauses / lulls
    hook_energy: float             # Average energy in first 0-3s


def analyze_audio_energy(
    video_or_audio_path: Path,
    hop_ms: int = 50,
    window_ms: int = 100,
    sample_rate: int = 16000,
) -> AudioEnergyProfile:
    """
    Extract raw PCM audio via FFmpeg pipe and compute RMS energy envelope,
    peak excitement spikes, and transient onsets.
    """
    video_or_audio_path = Path(video_or_audio_path)
    if not video_or_audio_path.exists():
        raise FileNotFoundError(f"Input file not found: {video_or_audio_path}")

    # Stream 16kHz mono 16-bit PCM directly from ffmpeg
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-i", str(video_or_audio_path),
        "-vn", "-f", "s16le", "-ac", "1", "-ar", str(sample_rate), "-"
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    raw_data, _ = proc.communicate()

    if not raw_data:
        # Fallback empty profile
        return AudioEnergyProfile(
            duration=0.0,
            sample_rate=sample_rate,
            rms_envelope=np.array([0.1], dtype=np.float32),
            time_points=np.array([0.0], dtype=np.float32),
            mean_energy=0.1,
            max_energy=0.1,
            energy_spikes=[],
            transient_onsets=[],
            quiet_valleys=[],
            hook_energy=0.1,
        )

    samples = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32) / 32768.0
    duration = len(samples) / float(sample_rate)

    win_samples = int(sample_rate * (window_ms / 1000.0))
    hop_samples = int(sample_rate * (hop_ms / 1000.0))

    if len(samples) < win_samples:
        return AudioEnergyProfile(
            duration=duration,
            sample_rate=sample_rate,
            rms_envelope=np.array([float(np.sqrt(np.mean(samples**2) + 1e-6))], dtype=np.float32),
            time_points=np.array([0.0], dtype=np.float32),
            mean_energy=0.1,
            max_energy=0.1,
            energy_spikes=[],
            transient_onsets=[],
            quiet_valleys=[],
            hook_energy=0.1,
        )

    # Compute moving RMS using valid convolution on squared samples
    sq = samples ** 2
    kernel = np.ones(win_samples, dtype=np.float32) / float(win_samples)
    conv = np.convolve(sq, kernel, mode="valid")
    # Subsample by hop_samples
    rms = np.sqrt(np.maximum(conv[::hop_samples], 1e-8))
    times = (np.arange(len(rms)) * hop_samples + (win_samples // 2)) / float(sample_rate)

    mean_rms = float(np.mean(rms))
    max_rms = float(np.max(rms))
    std_rms = float(np.std(rms))

    # 1. Detect Energy Spikes (Points where excitement/volume is > mean + 1.2 * std)
    spike_thresh = mean_rms + 1.15 * std_rms
    energy_spikes = []
    # Enforce minimum 1.5s separation between major spikes
    last_spike = -999.0
    for idx, (t, val) in enumerate(zip(times, rms)):
        if val >= spike_thresh and (t - last_spike) >= 1.5:
            # Check if it's a local maximum within +- 3 steps (150ms)
            s_idx = max(0, idx - 3)
            e_idx = min(len(rms), idx + 4)
            if val >= np.max(rms[s_idx:e_idx]):
                energy_spikes.append(round(float(t), 3))
                last_spike = t

    # 2. Detect Transient Onsets (Sharp positive jumps in RMS energy: dRMS/dt)
    diff_rms = np.diff(rms)
    transient_thresh = float(np.mean(diff_rms[diff_rms > 0]) + 1.8 * np.std(diff_rms[diff_rms > 0])) if np.any(diff_rms > 0) else 0.05
    transient_onsets = []
    last_transient = -999.0
    for idx, d_val in enumerate(diff_rms):
        t = times[idx]
        if d_val >= transient_thresh and (t - last_transient) >= 1.0:
            transient_onsets.append(round(float(t), 3))
            last_transient = t

    # 3. Detect Natural Quiet Valleys (Speech pauses, between sentences)
    quiet_thresh = mean_rms * 0.45
    quiet_valleys = []
    last_quiet = -999.0
    for t, val in zip(times, rms):
        if val <= quiet_thresh and (t - last_quiet) >= 2.0:
            quiet_valleys.append(round(float(t), 3))
            last_quiet = t

    # 4. Hook Energy (0.0s to 3.0s)
    hook_mask = times <= 3.0
    hook_energy = float(np.mean(rms[hook_mask])) if np.any(hook_mask) else mean_rms

    return AudioEnergyProfile(
        duration=round(duration, 3),
        sample_rate=sample_rate,
        rms_envelope=rms,
        time_points=times,
        mean_energy=round(mean_rms, 4),
        max_energy=round(max_rms, 4),
        energy_spikes=energy_spikes,
        transient_onsets=transient_onsets,
        quiet_valleys=quiet_valleys,
        hook_energy=round(hook_energy, 4),
    )
