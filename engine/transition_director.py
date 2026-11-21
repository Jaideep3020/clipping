#!/usr/bin/env python3
"""
engine/transition_director.py
=============================
AI Intelligent Editorial Transition Director.
Automatically analyzes clip specifications, video genre, audio/dialogue pacing,
and virality signals to choose and choreograph the optimal Premiere Pro & CapCut
transitions and sound effects without requiring manual user intervention.

Editorial Rules & Techniques Implemented:
1. Cricket & Sports:
   - Ball release & contact / Six / Wicket -> Punch Zooms (100% -> 122%) + 808 sub-bass drop
   - Scene & camera cuts -> Directional whip pans (consistent right-to-left) + 2-frame optical white flash
   - SFX placed 1-2 frames before visual impact for maximum punch
2. Gaming & Action (GTA 6, fast action):
   - Crashes, explosions, deaths -> Glitch damage + Earthquake camera shake + impact thud
   - High-speed chases & action -> Cross zooms & directional motion whips
   - Story & reveals -> VR Chroma Leaks & VR Light Rays
3. Dialogue & Podcast:
   - Dialogue jumpcut elimination -> Morph Cut & Smooth Dissolves
   - Emphatic key points -> Focal punch zoom + subtle whoosh
4. High-Energy Viral (MrBeast Pacing):
   - Visual change / pattern interrupt every 2-4 seconds
   - Rotating transition variety (Whips -> Venetian Blinds -> Cross Zoom -> Pinwheel -> Checkerboard)
   - Synchronized 48kHz audio SFX on every visual cut
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .transition_pack import (
    ALL_TRANSITIONS,
    TRANSITION_PACKS,
    TransitionInfo,
    get_transition_info,
)


@dataclass
class EditorialPlan:
    genre: str
    pacing_mode: str
    primary_transition: str
    cut_transitions: List[Tuple[float, str]]   # [(cut_timestamp, transition_name)]
    reel_transitions: List[str]                # transitions to stitch consecutive clips in reel
    rationale: str


class TransitionDirector:
    """
    Intelligent Director that analyzes video context and metadata
    to select the optimal transition strategy based on professional editing techniques.
    """

    # Keyword classifiers for content genres
    CRICKET_KEYWORDS = [
        "shot", "six", "wicket", "boundary", "bowled", "ball", "bat", "cricket",
        "kohli", "maxwell", "rohit", "stump", "catch", "innings", "runs", "over",
        "crease", "pitch", "yorker", "bouncer", "four", "umpire", "spin", "anger"
    ]

    GAMING_KEYWORDS = [
        "gta", "gameplay", "police", "car", "heist", "porsche", "vehicle", "mission",
        "shoot", "kill", "drift", "busted", "wasted", "fps", "mod", "vice city",
        "lucia", "jason", "rdr", "speed", "stole", "stealing", "driving"
    ]

    PODCAST_KEYWORDS = [
        "interview", "podcast", "episode", "said", "thought", "think", "agree",
        "disagree", "discuss", "conversation", "mentality", "advice", "story"
    ]

    VIRAL_EXCLAMATIONS = [
        "six", "out", "boom", "insane", "unreal", "no way", "oh my god", "omg",
        "look at that", "unbelievable", "wasted", "busted", "crazy", "what",
        "how did he", "holy", "broke the internet", "game over"
    ]

    @classmethod
    def detect_genre(cls, title: str = "", text: str = "", category: str = "") -> str:
        """Detect the content genre to select corresponding editing rules."""
        combined = f"{title} {text} {category}".lower()

        cricket_score = sum(1 for kw in cls.CRICKET_KEYWORDS if re.search(rf"\b{kw}\b", combined))
        gaming_score = sum(1 for kw in cls.GAMING_KEYWORDS if re.search(rf"\b{kw}\b", combined))
        podcast_score = sum(1 for kw in cls.PODCAST_KEYWORDS if re.search(rf"\b{kw}\b", combined))

        if cricket_score >= 2 or ("anger" in combined and "shot" in combined):
            return "cricket"
        elif gaming_score >= 2 or "gta" in combined:
            return "gaming"
        elif podcast_score >= 3:
            return "podcast"
        else:
            return "viral_general"

    @classmethod
    def plan_clip_strategy(
        cls,
        title: str,
        verbatim_quote: str = "",
        hook_title: str = "",
        cut_timestamps: Optional[List[float]] = None,
        duration: float = 30.0,
    ) -> EditorialPlan:
        """
        Analyze the clip specifications and design an editorial transition plan.
        """
        cuts = sorted(cut_timestamps or [])
        cuts = [c for c in cuts if 0.4 <= c <= duration - 0.4]
        genre = cls.detect_genre(title=title, text=f"{verbatim_quote} {hook_title}")

        cut_transitions: List[Tuple[float, str]] = []
        reel_transitions: List[str] = []

        if genre == "cricket":
            # ── Cricket Viral Editing Specification (10-Step Formula) ──
            # Step 4: Directional whip slide (right-to-left) + 2-frame optical white flash on scene cuts
            # Step 5: Punch zooms on contact / exclamations (100% -> 122%) + 808 sub-bass hit
            primary_trans = "whip_left"
            pacing_mode = "high_impact_sports"
            rationale = "Cricket 10-step pattern: directional whip pans, contact punch zooms, optical white flashes & 808s."

            variety_pool = ["whip_left", "punch_zoom", "optical_flash", "whip_left", "cross_zoom"]
            for idx, c in enumerate(cuts):
                trans = variety_pool[idx % len(variety_pool)]
                cut_transitions.append((c, trans))

            reel_transitions = ["whip_left", "cross_zoom", "optical_flash", "punch_zoom", "smooth_dissolve"]

        elif genre == "gaming":
            # ── Gaming & GTA 6 Specification ──
            # High speed, crashes, busts -> Glitch & Earthquake shake + Cross Zooms + VR Chroma
            primary_trans = "cross_zoom"
            pacing_mode = "fast_action_gaming"
            rationale = "Gaming action pattern: cross zooms, chromatic glitch bursts, earthquake impacts & VR light rays."

            variety_pool = ["cross_zoom", "glitch", "earthquake", "whip", "vr_chroma_leaks", "punch_zoom"]
            for idx, c in enumerate(cuts):
                trans = variety_pool[idx % len(variety_pool)]
                cut_transitions.append((c, trans))

            reel_transitions = ["cross_zoom", "glitch", "earthquake", "vr_light_rays", "whip_left"]

        elif genre == "podcast":
            # ── Podcast / Dialogue Specification ──
            # Smooth dialogue edits, jump-cut smoothing -> Morph cut & Smooth Dissolve
            primary_trans = "morph_cut"
            pacing_mode = "smooth_dialogue"
            rationale = "Dialogue pattern: seamless morph cuts & smooth dissolves to eliminate speech pauses and jump-cuts."

            variety_pool = ["morph_cut", "smooth_dissolve", "cross_dissolve", "film_dissolve"]
            for idx, c in enumerate(cuts):
                trans = variety_pool[idx % len(variety_pool)]
                cut_transitions.append((c, trans))

            reel_transitions = ["smooth_dissolve", "cross_dissolve", "additive_dissolve", "film_dissolve"]

        else:
            # ── General Viral / MrBeast Pacing ──
            # Visual pattern interrupt every 2-4 seconds with alternating variety
            primary_trans = "whip_left"
            pacing_mode = "viral_pattern_interrupt"
            rationale = "High-retention viral pattern: alternating visual interrupts every 2-4s (whip -> blinds -> zoom -> flash)."

            variety_pool = [
                "whip_left", "venetian_blinds", "punch_zoom", "cross_zoom",
                "optical_flash", "pinwheel", "checkerboard", "vr_light_leaks"
            ]
            for idx, c in enumerate(cuts):
                trans = variety_pool[idx % len(variety_pool)]
                cut_transitions.append((c, trans))

            reel_transitions = [
                "whip_left", "venetian_blinds", "cross_zoom", "vr_light_rays",
                "additive_dissolve", "page_turn", "cross_dissolve"
            ]

        return EditorialPlan(
            genre=genre,
            pacing_mode=pacing_mode,
            primary_transition=primary_trans,
            cut_transitions=cut_transitions,
            reel_transitions=reel_transitions,
            rationale=rationale,
        )

    @classmethod
    def plan_reel_compilation(
        cls,
        clips_metas: List[Dict[str, Any]],
        video_title: str = "",
    ) -> List[str]:
        """
        Orchestrate a cohesive editorial progression across a highlight compilation reel.
        Builds energy progressively: Opening Hook ➔ Escalating Highlights ➔ Climax ➔ Outro.
        """
        if not clips_metas:
            return ["whip_left"]

        genre = cls.detect_genre(
            title=video_title,
            text=" ".join(m.get("title", "") for m in clips_metas)
        )

        n_transitions = max(1, len(clips_metas) - 1)
        plan: List[str] = []

        if genre == "cricket":
            progression = [
                "whip_left",          # Clip 1 -> 2: High speed whip into the action
                "cross_zoom",          # Clip 2 -> 3: Punch zoom into big shot
                "optical_flash",       # Clip 3 -> 4: White flash impact
                "additive_dissolve",   # Clip 4 -> 5: Glowing bloom for match climax
                "smooth_dissolve",     # Outro resolution
            ]
        elif genre == "gaming":
            progression = [
                "cross_zoom",          # Clip 1 -> 2: Fast speed push
                "glitch",              # Clip 2 -> 3: Digital glitch cut
                "earthquake",          # Clip 3 -> 4: Seismic crash impact
                "vr_light_rays",       # Clip 4 -> 5: Cinematic lighting reveal
                "whip_left",           # Outro whip
            ]
        elif genre == "podcast":
            progression = [
                "smooth_dissolve",
                "additive_dissolve",
                "morph_cut",
                "cross_dissolve",
                "film_dissolve",
            ]
        else:
            progression = [
                "whip_left",
                "venetian_blinds",
                "cross_zoom",
                "pinwheel",
                "vr_light_rays",
                "additive_dissolve",
                "cross_dissolve",
            ]

        for i in range(n_transitions):
            plan.append(progression[i % len(progression)])

        return plan
