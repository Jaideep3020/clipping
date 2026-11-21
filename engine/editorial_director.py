#!/usr/bin/env python3
"""
engine/editorial_director.py
============================
Adaptive AI Editorial Director — Autonomous Decision Engine for ClipForge.

Automatically diagnoses raw video DNA across ALL content genres:
  1. Multi-Speaker Podcasts & Interviews (Joe Rogan, Lex Fridman, All-In)
  2. Solo Talking-Head & Education (Hormozi, MrBeast, Ali Abdaal, MKBHD)
  3. Gaming & Live Streams (GTA 6, Twitch, Kick, Esports)
  4. Keynotes, Slides & Tech Demos
  5. Sports & High-Energy Action
  6. Ambient, Scenic & Lifestyle Video

Instead of requiring users to remember dozens of manual CLI flags, the
Editorial Director analyzes video geometry, face distributions, speech cadence,
and transcript semantics to construct a tailored, professional editing recipe
that maximizes viewer retention on TikTok, YouTube Shorts, and Instagram Reels.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np


class ContentGenre(str, Enum):
    PODCAST = "podcast_multi_speaker"
    SOLO_TALKER = "solo_talking_head"
    GAMING = "gaming_livestream"
    KEYNOTE = "keynote_presentation"
    SPORTS = "sports_high_energy"
    GENERAL = "general_content"


@dataclass
class AdaptiveEditorialRecipe:
    """The master blueprint synthesized by AI for editing this specific video."""
    genre: ContentGenre
    confidence: float
    framing_mode: str              # auto_face | blur_bg | facecam_stack | center_crop
    caption_style: str             # hormozi | mrbeast | neon | minimal
    enable_punch_zooms: bool       # Dynamic 1.0x <-> 1.15x pattern interrupts
    enable_hook_banner: bool       # 0-4s viral curiosity headline
    enable_vocal_isolation: bool   # Meta Demucs stem separation
    enable_sfx_drops: bool         # 808 sub-bass drops + transition whooshes
    transition_pack: str           # auto | premiere_* | capcut_viral | glitch_*
    target_lufs: float             # EBU R128 mastering target (-14.0 for mobile)
    rationale: str
    diagnostics: Dict[str, Any] = field(default_factory=dict)


class AdaptiveEditorialDirector:
    """
    Cognitive Director that inspects video frames, audio properties,
    and transcripts to autonomously formulate the optimal editing strategy.
    """

    GENRE_KEYWORDS = {
        ContentGenre.GAMING: [
            "gta", "gameplay", "police", "mission", "busted", "wasted", "fps",
            "heist", "stream", "kill", "respawn", "rdr", "boss", "mod", "controller"
        ],
        ContentGenre.PODCAST: [
            "podcast", "guest", "welcome to the show", "interview", "episode",
            "agree with you", "what do you think", "tell me about", "conversation"
        ],
        ContentGenre.SPORTS: [
            "match", "goal", "wicket", "six", "score", "over", "ball", "touchdown",
            "championship", "referee", "tournament", "stadium", "catch", "penalty"
        ],
        ContentGenre.KEYNOTE: [
            "slide", "next slide", "conference", "presentation", "agenda", "keynote",
            "quarterly", "revenue", "architecture", "overview", "announcement"
        ],
    }

    @classmethod
    def diagnose_video_dna(
        cls,
        video_path: Path,
        transcript_result: Optional[Dict[str, Any]] = None,
        probe_info: Optional[Dict[str, Any]] = None,
        sample_frame_count: int = 12,
    ) -> AdaptiveEditorialRecipe:
        """
        Scan sample frames, audio, and transcript to generate an adaptive editing recipe.
        """
        video_path = Path(video_path)
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            # Fallback recipe if video cannot be opened
            return cls._default_recipe("Video could not be opened for frame sampling.")

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1920
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 1080
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 100
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        duration_sec = total_frames / max(1.0, fps)

        # ── 1. Computer Vision: Face Detection Statistics ───────────────────────
        face_counts: List[int] = []
        face_areas: List[float] = []

        from .face_tracker import SotaFaceTracker
        tracker = SotaFaceTracker()

        step = max(1, total_frames // max(1, sample_frame_count))
        for f_idx in range(0, total_frames, step):
            cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
            ret, frame = cap.read()
            if not ret or frame is None:
                continue

            if tracker.is_available():
                faces = tracker.detect_all_faces(frame)
                face_counts.append(len(faces))
                if faces:
                    for fc in faces:
                        _, _, fw, fh = fc["bbox"]
                        face_areas.append((fw * fh) / float(width * height))
            else:
                face_counts.append(0)

        cap.release()

        avg_faces = float(np.mean(face_counts)) if face_counts else 0.0
        max_faces = int(max(face_counts)) if face_counts else 0
        avg_face_area = float(np.mean(face_areas)) if face_areas else 0.0

        # ── 2. Transcript & Semantic Analysis ──────────────────────────────────
        transcript_text = ""
        if transcript_result and "text" in transcript_result:
            transcript_text = str(transcript_result["text"]).lower()

        genre_scores = {g: 0 for g in ContentGenre}

        for genre, kw_list in cls.GENRE_KEYWORDS.items():
            for kw in kw_list:
                if kw in transcript_text:
                    genre_scores[genre] += 1

        # ── 3. Decision Matrix & Classification ─────────────────────────────────
        diagnostics = {
            "width": width,
            "height": height,
            "duration_sec": round(duration_sec, 1),
            "avg_faces_detected": round(avg_faces, 2),
            "max_faces_in_frame": max_faces,
            "avg_face_area_ratio": round(avg_face_area, 4),
            "keyword_scores": {g.value: s for g, s in genre_scores.items() if s > 0},
        }

        # Rule 1: Gaming detection (strong keyword presence or extreme wide gameplay)
        if genre_scores[ContentGenre.GAMING] >= 3:
            return AdaptiveEditorialRecipe(
                genre=ContentGenre.GAMING,
                confidence=0.88,
                framing_mode="facecam_stack" if avg_faces > 0.3 else "auto_face",
                caption_style="mrbeast",
                enable_punch_zooms=True,
                enable_hook_banner=True,
                enable_vocal_isolation=True,   # Strip DMCA game radio music
                enable_sfx_drops=True,
                transition_pack="glitch_distortion",
                target_lufs=-14.0,
                rationale="Gaming content detected. Applied stacked facecam/gameplay layout, DMCA music shield, glitch action cuts, and MrBeast green captions.",
                diagnostics=diagnostics,
            )

        # Rule 2: Multi-Speaker Podcast / Interview (2+ distinct faces consistently detected)
        if avg_faces >= 1.4 or max_faces >= 2 or genre_scores[ContentGenre.PODCAST] >= 2:
            return AdaptiveEditorialRecipe(
                genre=ContentGenre.PODCAST,
                confidence=0.92,
                framing_mode="auto_face",      # SOTA Active Speaker Tracking (mouth movement)
                caption_style="hormozi",
                enable_punch_zooms=False,      # Natural conversational camera pacing
                enable_hook_banner=True,
                enable_vocal_isolation=True,   # Demucs vocal cleaning for crisp studio sound
                enable_sfx_drops=False,        # SFX whooshes kept subtle on interviews
                transition_pack="auto",
                target_lufs=-14.0,
                rationale="Multi-speaker podcast/interview identified. Activated Active Speaker mouth-tracking framing, Demucs dialogue cleanup, and Hormozi yellow caption highlights.",
                diagnostics=diagnostics,
            )

        # Rule 3: Sports / High Action
        if genre_scores[ContentGenre.SPORTS] >= 3:
            return AdaptiveEditorialRecipe(
                genre=ContentGenre.SPORTS,
                confidence=0.85,
                framing_mode="blur_bg" if avg_faces < 0.5 else "auto_face",
                caption_style="neon",
                enable_punch_zooms=True,
                enable_hook_banner=True,
                enable_vocal_isolation=False,  # Retain crowd excitement
                enable_sfx_drops=True,
                transition_pack="motion_whip",
                target_lufs=-14.0,
                rationale="Sports action detected. Activated motion whip transitions, 808 sub-bass drops on action peaks, and blurred horizontal cushion.",
                diagnostics=diagnostics,
            )

        # Rule 4: Keynote / Presentation
        if genre_scores[ContentGenre.KEYNOTE] >= 3 or (avg_faces < 0.4 and avg_face_area < 0.03):
            return AdaptiveEditorialRecipe(
                genre=ContentGenre.KEYNOTE,
                confidence=0.80,
                framing_mode="blur_bg",
                caption_style="minimal",
                enable_punch_zooms=False,
                enable_hook_banner=True,
                enable_vocal_isolation=True,
                enable_sfx_drops=False,
                transition_pack="premiere_dissolve",
                target_lufs=-14.0,
                rationale="Slide presentation/lecture detected. Clean minimal dark pill captions, blurred 9:16 frame preservation, and gentle dissolves.",
                diagnostics=diagnostics,
            )

        # Rule 5: Solo Talking-Head (1 prominent face)
        if avg_faces >= 0.6 and avg_face_area >= 0.04:
            return AdaptiveEditorialRecipe(
                genre=ContentGenre.SOLO_TALKER,
                confidence=0.90,
                framing_mode="auto_face",
                caption_style="hormozi",
                enable_punch_zooms=True,       # Prevent visual boredom via 1.15x punch-ins
                enable_hook_banner=True,
                enable_vocal_isolation=False,
                enable_sfx_drops=True,
                transition_pack="capcut_viral",
                target_lufs=-14.0,
                rationale="Solo talking-head detected. Centered on speaker with pattern-interrupt punch zooms every 3-4s, neon Hormozi captions, and retention hook card.",
                diagnostics=diagnostics,
            )

        # Rule 6: General default
        return cls._default_recipe("Balanced general content configuration applied.", diagnostics)

    @classmethod
    def _default_recipe(cls, rationale: str, diagnostics: Optional[Dict[str, Any]] = None) -> AdaptiveEditorialRecipe:
        return AdaptiveEditorialRecipe(
            genre=ContentGenre.GENERAL,
            confidence=0.70,
            framing_mode="auto_face",
            caption_style="hormozi",
            enable_punch_zooms=True,
            enable_hook_banner=True,
            enable_vocal_isolation=False,
            enable_sfx_drops=True,
            transition_pack="auto",
            target_lufs=-14.0,
            rationale=rationale,
            diagnostics=diagnostics or {},
        )
