#!/usr/bin/env python3
"""
engine/smart_sfx_designer.py
============================
Context-Aware Sound Design & SFX Synthesis Engine.
Synthesizes professional sound effects layer purely within FFmpeg (48kHz AAC)
and matches them directly to:
1. Dynamic transitions (whooshes, glitches, risers, thuds)
2. Real audio energy spikes and transient peaks (NO hardcoded timestamps!)
3. The 0-3s Opening Hook (808 Sub-Bass Impact)
"""

import subprocess
from pathlib import Path
from typing import List, Optional, Tuple
from .audio_beat_sync import AudioEnergyProfile, analyze_audio_energy
from .dynamic_transition_engine import CutTransitionAssignment


def synthesize_contextual_sfx(
    video_path: Path,
    output_sfx_path: Path,
    transition_schedule: List[CutTransitionAssignment],
    audio_profile: Optional[AudioEnergyProfile] = None,
    duration: Optional[float] = None,
    genre: str = "viral_general",
) -> Optional[Path]:
    """
    Generate an aligned, multi-layered SFX soundtrack for the video.
    Synthesizes each effect procedurally:
    - 808 Sub-bass boom on t=0 (The Hook Impact)
    - Directional whip whooshes at whip transitions
    - Glitch buzz chirps at glitch transitions
    - Impact thuds at camera shake / punch zoom moments
    - Accent impacts on real detected audio energy peaks
    """
    output_sfx_path = Path(output_sfx_path)
    output_sfx_path.parent.mkdir(parents=True, exist_ok=True)

    if audio_profile is None:
        audio_profile = analyze_audio_energy(video_path)

    total_dur = duration or audio_profile.duration
    if total_dur <= 0:
        return None

    fc_parts = []
    mix_inputs = []

    # ── 1. The Hook Impact: 808 Sub-Bass Drop at t=0.0s ──
    fc_parts.append(
        "aevalsrc=sin(2*PI*55*exp(-4.5*t)):d=0.60,lowpass=f=125,volume=2.2[boom_hook]"
    )
    mix_inputs.append("[boom_hook]")

    # ── 2. Transition-Matched SFX Layer ──
    for idx, item in enumerate(transition_schedule):
        c = item.timestamp
        sfx_t = item.sfx_type
        tag = f"sfx_trans_{idx}"

        # Lead time: sound hits ~80ms before cut point for maximum perceived impact
        delay_ms = max(0, int((c - 0.08) * 1000))

        if sfx_t == "whoosh":
            # Fast directional whoosh (bandpassed pink noise sweep)
            freq = 1150 if "left" in item.transition_type else 1350
            fc_parts.append(
                f"anoisesrc=c=pink:d=0.22,bandpass=f={freq}:width_type=q:w=2.2,volume=2.6,"
                f"afade=t=in:st=0:d=0.06,afade=t=out:st=0.08:d=0.14,"
                f"adelay={delay_ms}|{delay_ms}[{tag}]"
            )
            mix_inputs.append(f"[{tag}]")

        elif sfx_t == "boom" or sfx_t == "thud":
            # Snappy sub-thud
            fc_parts.append(
                f"aevalsrc=sin(2*PI*60*exp(-6*t)):d=0.35,lowpass=f=120,volume=2.0,"
                f"adelay={delay_ms}|{delay_ms}[{tag}]"
            )
            mix_inputs.append(f"[{tag}]")

        elif sfx_t == "glitch":
            # Digital data glitch chirp
            fc_parts.append(
                f"anoisesrc=c=white:d=0.14,bandpass=f=2800:width_type=q:w=4.0,volume=2.4,"
                f"aeval='val(0)*sin(2*PI*450*t)':d=0.14,"
                f"adelay={delay_ms}|{delay_ms}[{tag}]"
            )
            mix_inputs.append(f"[{tag}]")

        elif sfx_t == "flash":
            # Shimmer white flash riser
            fc_parts.append(
                f"anoisesrc=c=pink:d=0.20,bandpass=f=2400:width_type=q:w=1.8,volume=1.8,"
                f"afade=t=in:st=0:d=0.05,afade=t=out:st=0.06:d=0.14,"
                f"adelay={delay_ms}|{delay_ms}[{tag}]"
            )
            mix_inputs.append(f"[{tag}]")

    # ── 3. Real Audio Excitement / Transient Accents (NO hardcoded timestamps!) ──
    # Pick top detected energy spikes that are not already covered by a transition
    existing_times = [item.timestamp for item in transition_schedule]
    real_spikes = []
    for spk in audio_profile.energy_spikes:
        # If at least 1.0s away from any cut transition
        if all(abs(spk - ct) >= 1.0 for ct in existing_times):
            real_spikes.append(spk)

    for idx, spk_t in enumerate(real_spikes[:6]):  # Cap at top 6 moments
        if spk_t <= total_dur - 0.4:
            spk_d_ms = int(spk_t * 1000)
            tag_spk = f"accent_hit_{idx}"
            tag_wood = f"accent_wood_{idx}"

            if genre in ["sports", "cricket"]:
                # High-frequency transient click
                fc_parts.append(
                    f"anoisesrc=c=white:d=0.035,bandpass=f=2800:width_type=q:w=2.8,volume=4.5,"
                    f"adelay={spk_d_ms}|{spk_d_ms}[{tag_spk}]"
                )
                # Resonant acoustic pop
                fc_parts.append(
                    f"aevalsrc=sin(2*PI*560*t)*exp(-32*t):d=0.08,volume=3.6,"
                    f"adelay={spk_d_ms}|{spk_d_ms}[{tag_wood}]"
                )
                mix_inputs.append(f"[{tag_spk}]")
                mix_inputs.append(f"[{tag_wood}]")
            else:
                # Organic pop accent
                fc_parts.append(
                    f"aevalsrc=sin(2*PI*320*exp(-10*t)):d=0.10,volume=2.2,"
                    f"adelay={spk_d_ms}|{spk_d_ms}[{tag_spk}]"
                )
                mix_inputs.append(f"[{tag_spk}]")

    if not mix_inputs:
        return None

    # Mix down all generated SFX stems with volume ducking and EBU R128 loudness
    fc_parts.append(
        f"{''.join(mix_inputs)}amix=inputs={len(mix_inputs)}:normalize=0:dropout_transition=0,"
        f"loudnorm=I=-16:TP=-1.5:LRA=10[sfx_out]"
    )

    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-filter_complex", ";".join(fc_parts),
        "-map", "[sfx_out]",
        "-t", str(total_dur),
        "-c:a", "aac", "-b:a", "192k",
        str(output_sfx_path)
    ]

    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode == 0 and output_sfx_path.exists() and output_sfx_path.stat().st_size > 0:
        return output_sfx_path
    return None
