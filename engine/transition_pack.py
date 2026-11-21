#!/usr/bin/env python3
"""
engine/transition_pack.py
=========================
Comprehensive Transition Engine replicating the complete transition packs
of Adobe Premiere Pro and CapCut for short-form video & viral clipping.

Categories & Packs Included:
1. DISSOLVE: Additive Dissolve, Cross Dissolve, Dip to Black, Dip to White,
             Film Dissolve, Morph Cut, Non-Additive Dissolve, Smooth Dissolve
2. IMMERSIVE VIDEO (VR): VR Chroma Leaks, VR Gradient Wipe, VR Iris Wipe,
                         VR Light Leaks, VR Light Rays, VR Mobius Zoom,
                         VR Random Blocks, VR Spherical Blur
3. IRIS: Iris Box, Iris Cross, Iris Diamond, Iris Round
4. PAGE PEEL: Page Peel, Page Turn
5. SLIDE: Band Slide, Center Split, Push, Slide, Split, Whip
6. WIPE (16 Variations): Band Wipe, Barn Doors, Checker Wipe, Checkerboard,
                        Clock Wipe, Gradient Wipe, Inset, Multi-Wipe,
                        Paint Splatter, Pinwheel, Radial Wipe, Random Blocks Wipe,
                        Random Wipe, Spiral Boxes, Venetian Blinds, Wedge Wipe,
                        Zig-Zag Blocks
7. ZOOM & MOTION: Cross Zoom, Smooth Wipe, Motion Blur Dissolve
8. MODERN (2025+): Digital Glitch, Earthquake (Seismic Shake), VHS Damage,
                   Kaleidoscope, 3D Cube Spin
9. CAPCUT VIRAL: Whip Left/Right/Up/Down, Punch Zoom, Zoom In/Out, Optical Flash,
                 RGB Glitch, Impact Shake, Spin Zoom
"""

import json
import math
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .encoder_utils import get_h264_encoder_args, fallback_cmd_to_libx264


# ─────────────────────────────────────────────────────────────────────────────
# 1. Transition Definitions & Metadata
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TransitionInfo:
    name: str
    display_name: str
    pack: str
    category: str
    description: str
    default_duration: float
    sfx_type: str  # 'whoosh', 'boom', 'glitch', 'flash', 'thud', 'riser', 'paper'
    xfade_type: Optional[str] = None      # Built-in ffmpeg xfade name if applicable
    custom_expr: Optional[str] = None     # Mathematical pixel mapping expression for custom xfade


ALL_TRANSITIONS: Dict[str, TransitionInfo] = {
    # ═════════════════════════════════════════════════════════════════════════
    # 1. DISSOLVE
    # ═════════════════════════════════════════════════════════════════════════
    "cross_dissolve": TransitionInfo(
        name="cross_dissolve",
        display_name="Premiere Cross Dissolve",
        pack="premiere_dissolve",
        category="Dissolve",
        description="Classic smooth linear opacity crossfade between outgoing and incoming clips.",
        default_duration=0.40,
        sfx_type="whoosh",
        xfade_type="dissolve",
    ),
    "additive_dissolve": TransitionInfo(
        name="additive_dissolve",
        display_name="Premiere Additive Dissolve",
        pack="premiere_dissolve",
        category="Dissolve",
        description="Colors of both clips are added together, creating a bright glowing bloom during transition.",
        default_duration=0.35,
        sfx_type="flash",
        custom_expr="clip(A*(1-P)+B*P + min(A\\,B)*(1-abs(2*P-1))*0.85\\, 0\\, 255)",
    ),
    "dip_to_black": TransitionInfo(
        name="dip_to_black",
        display_name="Premiere Dip to Black",
        pack="premiere_dissolve",
        category="Dissolve",
        description="Fades outgoing clip fully to black before fading up into the incoming clip.",
        default_duration=0.40,
        sfx_type="whoosh",
        xfade_type="fadeblack",
    ),
    "dip_to_white": TransitionInfo(
        name="dip_to_white",
        display_name="Premiere Dip to White",
        pack="premiere_dissolve",
        category="Dissolve",
        description="Fades outgoing clip through an intense white highlight before resolving to incoming clip.",
        default_duration=0.30,
        sfx_type="flash",
        xfade_type="fadewhite",
    ),
    "film_dissolve": TransitionInfo(
        name="film_dissolve",
        display_name="Premiere Film Dissolve",
        pack="premiere_dissolve",
        category="Dissolve",
        description="Non-linear film gamma crossfade preserving midtone contrast and organic highlight roll-off.",
        default_duration=0.40,
        sfx_type="whoosh",
        xfade_type="fadegrays",
    ),
    "morph_cut": TransitionInfo(
        name="morph_cut",
        display_name="Premiere Morph Cut (Optical Blend)",
        pack="premiere_dissolve",
        category="Dissolve",
        description="Seamless perceptual interpolation blend designed to eliminate jump-cuts in talking-head footage.",
        default_duration=0.25,
        sfx_type="whoosh",
        custom_expr="A*(1-P) + B*P",
    ),
    "non_additive_dissolve": TransitionInfo(
        name="non_additive_dissolve",
        display_name="Premiere Non-Additive Dissolve",
        pack="premiere_dissolve",
        category="Dissolve",
        description="Pixel-by-pixel luminance comparison showing the brighter clip as the threshold shifts.",
        default_duration=0.35,
        sfx_type="whoosh",
        custom_expr="if(gt(A*(1-P)\\, B*P)\\, A\\, B)",
    ),
    "smooth_dissolve": TransitionInfo(
        name="smooth_dissolve",
        display_name="Premiere Smooth Dissolve",
        pack="premiere_dissolve",
        category="Dissolve",
        description="Smooth cubic S-curve ease-in-out dissolve without harsh start or stop points.",
        default_duration=0.40,
        sfx_type="whoosh",
        custom_expr="A*(1-(3*P*P-2*P*P*P)) + B*(3*P*P-2*P*P*P)",
    ),

    # ═════════════════════════════════════════════════════════════════════════
    # 2. IMMERSIVE VIDEO (VR)
    # ═════════════════════════════════════════════════════════════════════════
    "vr_chroma_leaks": TransitionInfo(
        name="vr_chroma_leaks",
        display_name="Premiere VR Chroma Leaks",
        pack="premiere_immersive_vr",
        category="Immersive Video (VR)",
        description="Spherical chromatic aberration color split with red/blue channel leakage.",
        default_duration=0.35,
        sfx_type="glitch",
        custom_expr="clip(if(eq(PLANE\\,0)\\, a0(X-W*P*0.06\\, Y)*(1-P) + b0(X+W*(1-P)*0.06\\, Y)*P\\, if(eq(PLANE\\,1)\\, A*(1-P) + B*P\\, a2(X+W*P*0.06\\, Y)*(1-P) + b2(X-W*(1-P)*0.06\\, Y)*P)) + 40*sin(PI*P)\\, 0\\, 255)",
    ),
    "vr_gradient_wipe": TransitionInfo(
        name="vr_gradient_wipe",
        display_name="Premiere VR Gradient Wipe",
        pack="premiere_immersive_vr",
        category="Immersive Video (VR)",
        description="Spherical cosine gradient wipe sweeping across 360 panoramic space.",
        default_duration=0.40,
        sfx_type="whoosh",
        custom_expr="if(lt(0.5*(1+cos(PI*(X/W-P))) + (Y/H)*0.2\\, 1.0)\\, B\\, A)",
    ),
    "vr_iris_wipe": TransitionInfo(
        name="vr_iris_wipe",
        display_name="Premiere VR Iris Wipe",
        pack="premiere_immersive_vr",
        category="Immersive Video (VR)",
        description="Expanding spherical fish-eye circular iris revealing the incoming scene.",
        default_duration=0.40,
        sfx_type="whoosh",
        xfade_type="circleopen",
    ),
    "vr_light_leaks": TransitionInfo(
        name="vr_light_leaks",
        display_name="Premiere VR Light Leaks",
        pack="premiere_immersive_vr",
        category="Immersive Video (VR)",
        description="Warm analog film burn light leak sweeping across panoramic coordinates.",
        default_duration=0.35,
        sfx_type="riser",
        custom_expr="clip(A*(1-P) + B*P + 80*sin(PI*P)*exp(-pow((X/W-P)*3\\,2))\\, 0\\, 255)",
    ),
    "vr_light_rays": TransitionInfo(
        name="vr_light_rays",
        display_name="Premiere VR Light Rays",
        pack="premiere_immersive_vr",
        category="Immersive Video (VR)",
        description="Volumetric anamorphic light rays radiating from the center of the transition.",
        default_duration=0.35,
        sfx_type="flash",
        custom_expr="clip(A*(1-P) + B*P + 95*sin(PI*P)*pow(abs(cos(atan2(Y-H/2\\,X-W/2)*8))\\, 3)\\, 0\\, 255)",
    ),
    "vr_mobius_zoom": TransitionInfo(
        name="vr_mobius_zoom",
        display_name="Premiere VR Mobius Zoom",
        pack="premiere_immersive_vr",
        category="Immersive Video (VR)",
        description="Mobius mathematical swirl transformation twisting into the new scene.",
        default_duration=0.40,
        sfx_type="whoosh",
        xfade_type="radial",
    ),
    "vr_random_blocks": TransitionInfo(
        name="vr_random_blocks",
        display_name="Premiere VR Random Blocks",
        pack="premiere_immersive_vr",
        category="Immersive Video (VR)",
        description="Procedural 360-degree randomized digital block noise dissolving between clips.",
        default_duration=0.35,
        sfx_type="glitch",
        custom_expr="if(lt(mod(sin(floor(X/32)*12.9898 + floor(Y/32)*78.233)*43758.5453\\, 1)\\, P)\\, B\\, A)",
    ),
    "vr_spherical_blur": TransitionInfo(
        name="vr_spherical_blur",
        display_name="Premiere VR Spherical Blur",
        pack="premiere_immersive_vr",
        category="Immersive Video (VR)",
        description="Spherical panoramic equirectangular blur dissolve linking two scenes.",
        default_duration=0.35,
        sfx_type="whoosh",
        xfade_type="hblur",
    ),

    # ═════════════════════════════════════════════════════════════════════════
    # 3. IRIS
    # ═════════════════════════════════════════════════════════════════════════
    "iris_box": TransitionInfo(
        name="iris_box",
        display_name="Premiere Iris Box",
        pack="premiere_iris",
        category="Iris",
        description="Expanding rectangular iris aperture revealing incoming shot.",
        default_duration=0.35,
        sfx_type="whoosh",
        xfade_type="rectcrop",
    ),
    "iris_cross": TransitionInfo(
        name="iris_cross",
        display_name="Premiere Iris Cross",
        pack="premiere_iris",
        category="Iris",
        description="Expanding cross (+) aperture uncovering the incoming shot from the center.",
        default_duration=0.35,
        sfx_type="whoosh",
        custom_expr="if(max(lt(abs(X-W/2)\\, W*P*0.5)\\, lt(abs(Y-H/2)\\, H*P*0.5))\\, B\\, A)",
    ),
    "iris_diamond": TransitionInfo(
        name="iris_diamond",
        display_name="Premiere Iris Diamond",
        pack="premiere_iris",
        category="Iris",
        description="Expanding diamond aperture (rotated 45° box) centered on the subject.",
        default_duration=0.35,
        sfx_type="whoosh",
        custom_expr="if(lt(abs(X-W/2)/(W/2) + abs(Y-H/2)/(H/2)\\, P*2)\\, B\\, A)",
    ),
    "iris_round": TransitionInfo(
        name="iris_round",
        display_name="Premiere Iris Round",
        pack="premiere_iris",
        category="Iris",
        description="Expanding circular iris aperture revealing incoming shot.",
        default_duration=0.35,
        sfx_type="whoosh",
        xfade_type="circleopen",
    ),

    # ═════════════════════════════════════════════════════════════════════════
    # 4. PAGE PEEL
    # ═════════════════════════════════════════════════════════════════════════
    "page_peel": TransitionInfo(
        name="page_peel",
        display_name="Premiere Page Peel",
        pack="premiere_page_peel",
        category="Page Peel",
        description="Bottom corner curls up and peels diagonally like glossy magazine paper.",
        default_duration=0.45,
        sfx_type="paper",
        xfade_type="diagtl",
    ),
    "page_turn": TransitionInfo(
        name="page_turn",
        display_name="Premiere Page Turn",
        pack="premiere_page_peel",
        category="Page Peel",
        description="Book-style diagonal page turn uncovering the next scene.",
        default_duration=0.45,
        sfx_type="paper",
        xfade_type="diagtr",
    ),

    # ═════════════════════════════════════════════════════════════════════════
    # 5. SLIDE
    # ═════════════════════════════════════════════════════════════════════════
    "band_slide": TransitionInfo(
        name="band_slide",
        display_name="Premiere Band Slide",
        pack="premiere_slide",
        category="Slide",
        description="Alternating horizontal shutter bands sliding in from opposite directions.",
        default_duration=0.35,
        sfx_type="whoosh",
        xfade_type="hlslice",
    ),
    "center_split": TransitionInfo(
        name="center_split",
        display_name="Premiere Center Split",
        pack="premiere_slide",
        category="Slide",
        description="Screen splits apart from the center outward to reveal the incoming scene.",
        default_duration=0.35,
        sfx_type="whoosh",
        xfade_type="vertclose",
    ),
    "push": TransitionInfo(
        name="push",
        display_name="Premiere Push",
        pack="premiere_slide",
        category="Slide",
        description="Incoming frame pushes the outgoing frame out of the viewing canvas.",
        default_duration=0.35,
        sfx_type="whoosh",
        xfade_type="slideleft",
    ),
    "slide": TransitionInfo(
        name="slide",
        display_name="Premiere Slide",
        pack="premiere_slide",
        category="Slide",
        description="Incoming frame slides over top of the outgoing frame.",
        default_duration=0.35,
        sfx_type="whoosh",
        xfade_type="coverleft",
    ),
    "split": TransitionInfo(
        name="split",
        display_name="Premiere Split",
        pack="premiere_slide",
        category="Slide",
        description="Screen splits down the middle opening outward like double doors.",
        default_duration=0.35,
        sfx_type="whoosh",
        xfade_type="vertopen",
    ),
    "whip": TransitionInfo(
        name="whip",
        display_name="Premiere Whip",
        pack="premiere_slide",
        category="Slide",
        description="High-speed directional whip pan slide with motion blur displacement.",
        default_duration=0.24,
        sfx_type="whoosh",
        xfade_type="smoothleft",
    ),

    # ═════════════════════════════════════════════════════════════════════════
    # 6. WIPE (16 Premiere Pro Variations)
    # ═════════════════════════════════════════════════════════════════════════
    "band_wipe": TransitionInfo(
        name="band_wipe",
        display_name="Premiere Band Wipe",
        pack="premiere_wipe",
        category="Wipe",
        description="Multi-band horizontal slats uncover the incoming frame in sections.",
        default_duration=0.35,
        sfx_type="whoosh",
        xfade_type="hlslice",
    ),
    "barn_doors": TransitionInfo(
        name="barn_doors",
        display_name="Premiere Barn Doors",
        pack="premiere_wipe",
        category="Wipe",
        description="Vertical barn doors opening outward from the center seam.",
        default_duration=0.35,
        sfx_type="whoosh",
        xfade_type="vertopen",
    ),
    "checker_wipe": TransitionInfo(
        name="checker_wipe",
        display_name="Premiere Checker Wipe",
        pack="premiere_wipe",
        category="Wipe",
        description="Checkerboard pattern wipe revealing the next scene in alternating blocks.",
        default_duration=0.35,
        sfx_type="whoosh",
        custom_expr="if(lt(X/W + mod(floor(X/64)+floor(Y/64)\\, 2)*0.25\\, P*1.25)\\, B\\, A)",
    ),
    "checkerboard": TransitionInfo(
        name="checkerboard",
        display_name="Premiere Checkerboard",
        pack="premiere_wipe",
        category="Wipe",
        description="Multi-tile mosaic checkerboard dissolve across the full frame.",
        default_duration=0.35,
        sfx_type="whoosh",
        custom_expr="if(lt(mod(floor(X/48)*17 + floor(Y/48)*31\\, 100)/100.0\\, P)\\, B\\, A)",
    ),
    "clock_wipe": TransitionInfo(
        name="clock_wipe",
        display_name="Premiere Clock Wipe",
        pack="premiere_wipe",
        category="Wipe",
        description="Clock-hand 360-degree circular sweep around the center axis.",
        default_duration=0.40,
        sfx_type="whoosh",
        xfade_type="radial",
    ),
    "gradient_wipe": TransitionInfo(
        name="gradient_wipe",
        display_name="Premiere Gradient Wipe",
        pack="premiere_wipe",
        category="Wipe",
        description="Soft directional luminance gradient ramp uncover.",
        default_duration=0.35,
        sfx_type="whoosh",
        custom_expr="if(lt(X/W + (Y/H)*0.5\\, P*1.5)\\, B\\, A)",
    ),
    "inset": TransitionInfo(
        name="inset",
        display_name="Premiere Inset",
        pack="premiere_wipe",
        category="Wipe",
        description="Inset rectangular aperture expanding from the corner into full frame.",
        default_duration=0.35,
        sfx_type="whoosh",
        xfade_type="rectcrop",
    ),
    "multi_wipe": TransitionInfo(
        name="multi_wipe",
        display_name="Premiere Multi-Wipe",
        pack="premiere_wipe",
        category="Wipe",
        description="Multiple simultaneous linear wipes sweeping across parallel sectors.",
        default_duration=0.35,
        sfx_type="whoosh",
        xfade_type="hrslice",
    ),
    "paint_splatter": TransitionInfo(
        name="paint_splatter",
        display_name="Premiere Paint Splatter",
        pack="premiere_wipe",
        category="Wipe",
        description="Procedural organic paint splatter droplets uncovering the new clip.",
        default_duration=0.35,
        sfx_type="whoosh",
        custom_expr="if(lt(mod(sin(X*12.9898 + Y*78.233)*43758.5453\\, 1)*0.35 + (X/W)\\, P*1.35)\\, B\\, A)",
    ),
    "pinwheel": TransitionInfo(
        name="pinwheel",
        display_name="Premiere Pinwheel",
        pack="premiere_wipe",
        category="Wipe",
        description="Four rotating pinwheel blades sweeping simultaneously across quadrants.",
        default_duration=0.40,
        sfx_type="whoosh",
        custom_expr="if(lt(mod(atan2(Y-H/2\\, X-W/2)+PI\\, PI/2)/(PI/2)\\, P)\\, B\\, A)",
    ),
    "radial_wipe": TransitionInfo(
        name="radial_wipe",
        display_name="Premiere Radial Wipe",
        pack="premiere_wipe",
        category="Wipe",
        description="Circular radial wipe sweeping clockwise around the frame center.",
        default_duration=0.40,
        sfx_type="whoosh",
        xfade_type="radial",
    ),
    "random_blocks_wipe": TransitionInfo(
        name="random_blocks_wipe",
        display_name="Premiere Random Blocks Wipe",
        pack="premiere_wipe",
        category="Wipe",
        description="Random digital block grid dissolving progressively into the new shot.",
        default_duration=0.35,
        sfx_type="glitch",
        xfade_type="pixelize",
    ),
    "random_wipe": TransitionInfo(
        name="random_wipe",
        display_name="Premiere Random Wipe",
        pack="premiere_wipe",
        category="Wipe",
        description="Procedural dither scatter noise wipe uncovering pixels randomly.",
        default_duration=0.35,
        sfx_type="glitch",
        custom_expr="if(lt(mod(sin(X*93.1 + Y*47.3)*1000\\, 1)\\, P)\\, B\\, A)",
    ),
    "spiral_boxes": TransitionInfo(
        name="spiral_boxes",
        display_name="Premiere Spiral Boxes",
        pack="premiere_wipe",
        category="Wipe",
        description="Spiral rectangular aperture expanding outwards from the center.",
        default_duration=0.35,
        sfx_type="whoosh",
        xfade_type="circlecrop",
    ),
    "venetian_blinds": TransitionInfo(
        name="venetian_blinds",
        display_name="Premiere Venetian Blinds",
        pack="premiere_wipe",
        category="Wipe",
        description="Horizontal multi-slat Venetian blinds rotating open to reveal the incoming scene.",
        default_duration=0.35,
        sfx_type="whoosh",
        custom_expr="if(lt(mod(Y\\, H/16)/(H/16)\\, P)\\, B\\, A)",
    ),
    "wedge_wipe": TransitionInfo(
        name="wedge_wipe",
        display_name="Premiere Wedge Wipe",
        pack="premiere_wipe",
        category="Wipe",
        description="Angular wedge opening outwards like fan blades uncovering the scene.",
        default_duration=0.35,
        sfx_type="whoosh",
        custom_expr="if(lt(abs(atan2(Y-H/2\\, X-W/2))\\, PI*P)\\, B\\, A)",
    ),
    "zig_zag_blocks": TransitionInfo(
        name="zig_zag_blocks",
        display_name="Premiere Zig-Zag Blocks",
        pack="premiere_wipe",
        category="Wipe",
        description="Stepping zig-zag multi-block geometric wipe across the frame.",
        default_duration=0.35,
        sfx_type="whoosh",
        custom_expr="if(lt(X/W + mod(floor(Y/32)\\, 4)*0.1\\, P*1.4)\\, B\\, A)",
    ),

    # ═════════════════════════════════════════════════════════════════════════
    # 7. ZOOM & MOTION
    # ═════════════════════════════════════════════════════════════════════════
    "cross_zoom": TransitionInfo(
        name="cross_zoom",
        display_name="Premiere Cross Zoom",
        pack="premiere_zoom_motion",
        category="Zoom & Motion",
        description="Rapid exponential zoom pop punching through into the incoming frame.",
        default_duration=0.35,
        sfx_type="boom",
        xfade_type="zoomin",
    ),
    "smooth_wipe": TransitionInfo(
        name="smooth_wipe",
        display_name="Premiere Smooth Wipe",
        pack="premiere_zoom_motion",
        category="Zoom & Motion",
        description="Smooth ease-in-out directional slide wipe with softened edge boundary.",
        default_duration=0.35,
        sfx_type="whoosh",
        xfade_type="smoothleft",
    ),
    "motion_blur": TransitionInfo(
        name="motion_blur",
        display_name="Premiere Motion Blur Dissolve",
        pack="premiere_zoom_motion",
        category="Zoom & Motion",
        description="High-speed horizontal motion blur dissolve linking two dynamic action scenes.",
        default_duration=0.35,
        sfx_type="whoosh",
        xfade_type="hblur",
    ),

    # ═════════════════════════════════════════════════════════════════════════
    # 8. MODERN ADDITIONS (2025+)
    # ═════════════════════════════════════════════════════════════════════════
    "glitch": TransitionInfo(
        name="glitch",
        display_name="Premiere 2025 Glitch Damage",
        pack="premiere_modern_2025",
        category="Modern (2025+)",
        description="Digital signal distortion, chromatic RGB channel offset, and electronic noise burst.",
        default_duration=0.25,
        sfx_type="glitch",
    ),
    "earthquake": TransitionInfo(
        name="earthquake",
        display_name="Premiere 2025 Earthquake (Seismic Shake)",
        pack="premiere_modern_2025",
        category="Modern (2025+)",
        description="Violent multi-axis seismic camera shake oscillation decaying on transition impact.",
        default_duration=0.35,
        sfx_type="thud",
    ),
    "vhs_damage": TransitionInfo(
        name="vhs_damage",
        display_name="Premiere 2025 VHS Damage & Tracking",
        pack="premiere_modern_2025",
        category="Modern (2025+)",
        description="Retro analog VHS tracking head tear, scanline roll, and tape dropout noise.",
        default_duration=0.30,
        sfx_type="glitch",
    ),
    "kaleidoscope": TransitionInfo(
        name="kaleidoscope",
        display_name="Premiere 2025 Kaleidoscope",
        pack="premiere_modern_2025",
        category="Modern (2025+)",
        description="Quad-radial optical mirror symmetry reflection warping into the incoming frame.",
        default_duration=0.40,
        sfx_type="whoosh",
        custom_expr="clip(if(lt(P\\,0.5)\\, a0(abs(X-W/2)*2\\, abs(Y-H/2)*2)*(1-2*P) + b0(W/2-abs(X-W/2)\\, H/2-abs(Y-H/2))*2*P\\, B)\\, 0\\, 255)",
    ),
    "cube_spin": TransitionInfo(
        name="cube_spin",
        display_name="Premiere 2025 3D Cube Spin",
        pack="premiere_modern_2025",
        category="Modern (2025+)",
        description="3D horizontal cube rotation perspective flip uncovering the adjacent face.",
        default_duration=0.35,
        sfx_type="whoosh",
        xfade_type="squeezeh",
    ),

    # ═════════════════════════════════════════════════════════════════════════
    # 9. CAPCUT VIRAL SHORT-FORM PACK
    # ═════════════════════════════════════════════════════════════════════════
    "whip_left": TransitionInfo(
        name="whip_left",
        display_name="CapCut Whip Left",
        pack="capcut_viral",
        category="Whip / Movement",
        description="High-speed right-to-left whip pan with directional motion displacement and white flash.",
        default_duration=0.24,
        sfx_type="whoosh",
        xfade_type="smoothleft",
    ),
    "whip_right": TransitionInfo(
        name="whip_right",
        display_name="CapCut Whip Right",
        pack="capcut_viral",
        category="Whip / Movement",
        description="High-speed left-to-right whip pan with directional motion displacement.",
        default_duration=0.24,
        sfx_type="whoosh",
        xfade_type="smoothright",
    ),
    "whip_up": TransitionInfo(
        name="whip_up",
        display_name="CapCut Whip Up",
        pack="capcut_viral",
        category="Whip / Movement",
        description="Fast upward whip transition with vertical displacement.",
        default_duration=0.24,
        sfx_type="whoosh",
        xfade_type="smoothup",
    ),
    "whip_down": TransitionInfo(
        name="whip_down",
        display_name="CapCut Whip Down",
        pack="capcut_viral",
        category="Whip / Movement",
        description="Fast downward whip transition with vertical displacement.",
        default_duration=0.24,
        sfx_type="whoosh",
        xfade_type="smoothdown",
    ),
    "punch_zoom": TransitionInfo(
        name="punch_zoom",
        display_name="CapCut / Premiere Punch Zoom",
        pack="capcut_viral",
        category="Zoom",
        description="Rapid 100% -> 125% -> 100% zoom pop drawing immediate focus to the action.",
        default_duration=0.35,
        sfx_type="boom",
        xfade_type="zoomin",
    ),
    "zoom_in": TransitionInfo(
        name="zoom_in",
        display_name="CapCut Zoom In (Pull In)",
        pack="capcut_viral",
        category="Zoom",
        description="Exponential scale-in transition passing through the frame into the next shot.",
        default_duration=0.40,
        sfx_type="whoosh",
        xfade_type="zoomin",
    ),
    "zoom_out": TransitionInfo(
        name="zoom_out",
        display_name="CapCut Zoom Out (Pull Back)",
        pack="capcut_viral",
        category="Zoom",
        description="Starts tightly zoomed in and snaps out to full wide framing.",
        default_duration=0.40,
        sfx_type="whoosh",
        xfade_type="distance",
    ),
    "optical_flash": TransitionInfo(
        name="optical_flash",
        display_name="CapCut White Flash",
        pack="capcut_viral",
        category="Light & Flash",
        description="2-frame intense optical white flash pop at transition midpoint.",
        default_duration=0.15,
        sfx_type="flash",
        xfade_type="fadewhite",
    ),
    "rgb_glitch": TransitionInfo(
        name="rgb_glitch",
        display_name="CapCut RGB Split Glitch",
        pack="capcut_viral",
        category="Glitch",
        description="Chromatic aberration color channel displacement (red/blue split) across the cut.",
        default_duration=0.20,
        sfx_type="glitch",
    ),
    "camera_shake": TransitionInfo(
        name="camera_shake",
        display_name="CapCut Impact Shake",
        pack="capcut_viral",
        category="Distortion",
        description="High-frequency camera shake oscillation decaying upon transition impact.",
        default_duration=0.30,
        sfx_type="thud",
    ),
    "light_leak": TransitionInfo(
        name="light_leak",
        display_name="CapCut Film Burn / Light Leak",
        pack="capcut_viral",
        category="Light & Flash",
        description="Warm amber/orange analog film burn glow dissolving between scenes.",
        default_duration=0.35,
        sfx_type="riser",
        custom_expr="clip(A*(1-P) + B*P + 80*sin(PI*P)*exp(-pow((X/W-P)*3\\,2))\\, 0\\, 255)",
    ),
    "spin_zoom": TransitionInfo(
        name="spin_zoom",
        display_name="CapCut Spin Zoom (Swirl)",
        pack="capcut_viral",
        category="Movement / Spin",
        description="Fast 180° rotation combined with scale zoom.",
        default_duration=0.35,
        sfx_type="whoosh",
        xfade_type="radial",
    ),
}

# Group transitions into curated packs matching user requests
TRANSITION_PACKS: Dict[str, List[str]] = {
    # ── Official Premiere Pro Categories ──
    "premiere_dissolve": [
        "cross_dissolve", "additive_dissolve", "dip_to_black", "dip_to_white",
        "film_dissolve", "morph_cut", "non_additive_dissolve", "smooth_dissolve"
    ],
    "premiere_immersive_vr": [
        "vr_chroma_leaks", "vr_gradient_wipe", "vr_iris_wipe", "vr_light_leaks",
        "vr_light_rays", "vr_mobius_zoom", "vr_random_blocks", "vr_spherical_blur"
    ],
    "premiere_iris": [
        "iris_round", "iris_box", "iris_cross", "iris_diamond"
    ],
    "premiere_page_peel": [
        "page_peel", "page_turn"
    ],
    "premiere_slide": [
        "push", "slide", "whip", "band_slide", "split", "center_split"
    ],
    "premiere_wipe": [
        "radial_wipe", "clock_wipe", "barn_doors", "band_wipe", "checkerboard",
        "checker_wipe", "gradient_wipe", "venetian_blinds", "paint_splatter",
        "pinwheel", "random_blocks_wipe", "random_wipe", "inset", "multi_wipe",
        "spiral_boxes", "wedge_wipe", "zig_zag_blocks"
    ],
    "premiere_zoom_motion": [
        "cross_zoom", "smooth_wipe", "motion_blur"
    ],
    "premiere_modern_2025": [
        "glitch", "earthquake", "vhs_damage", "kaleidoscope", "cube_spin"
    ],
    "premiere_pro_all": [
        "cross_dissolve", "whip", "cross_zoom", "additive_dissolve", "vr_chroma_leaks",
        "vr_light_leaks", "iris_cross", "iris_diamond", "venetian_blinds", "checkerboard",
        "pinwheel", "glitch", "earthquake", "page_peel"
    ],

    # ── CapCut Viral Packs ──
    "capcut_viral": [
        "whip_left", "whip_right", "whip_up", "whip_down",
        "punch_zoom", "zoom_in", "zoom_out", "optical_flash",
        "rgb_glitch", "camera_shake", "light_leak", "spin_zoom"
    ],
    "glitch_distortion": [
        "glitch", "rgb_glitch", "earthquake", "vhs_damage", "vr_random_blocks"
    ],
    "motion_whip": [
        "whip", "whip_left", "whip_right", "whip_up", "whip_down", "spin_zoom"
    ],
    "cinematic_light": [
        "vr_light_leaks", "vr_light_rays", "light_leak", "optical_flash", "dip_to_white"
    ],
    "slice_wind": [
        "band_wipe", "band_slide", "venetian_blinds", "multi_wipe"
    ],
}


def get_available_packs() -> Dict[str, List[str]]:
    return TRANSITION_PACKS


def get_transition_info(name: str) -> Optional[TransitionInfo]:
    return ALL_TRANSITIONS.get(name.lower().strip())


# ─────────────────────────────────────────────────────────────────────────────
# 2. Synchronized SFX Synthesizer for Transitions
# ─────────────────────────────────────────────────────────────────────────────

def generate_transition_sfx(
    sfx_type: str,
    output_path: Path,
    duration: float = 0.35,
    sample_rate: int = 48000,
) -> Path:
    """
    Synthesize high-fidelity sound effects matching each transition type:
    - whoosh: Fast frequency-swept rising pink noise whoosh
    - boom: Heavy 808 sub-bass drop impact
    - flash: Camera flash & high-pitched acoustic click
    - glitch: Digital glitch click + electrical buzz
    - thud: Low frequency camera shake thud
    - riser: Warm ambient riser for light leaks
    - paper: Crisp paper rustle for page peels and turns
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    sfx = sfx_type.lower().strip()
    if sfx == "whoosh":
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i",
            f"anoisesrc=c=pink:d={duration:.3f}:r={sample_rate},"
            f"bandpass=f=1200:width_type=q:w=2.4,volume=3.0,"
            f"afade=t=in:st=0:d={duration*0.3:.3f},afade=t=out:st={duration*0.4:.3f}:d={duration*0.6:.3f}",
            "-c:a", "aac", "-b:a", "192k",
            str(output_path),
        ]
    elif sfx == "boom":
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i",
            f"aevalsrc=sin(2*PI*55*exp(-4.5*t)):d={duration:.3f}:s={sample_rate},"
            f"lowpass=f=130,volume=2.6,afade=t=out:st={duration*0.4:.3f}:d={duration*0.6:.3f}",
            "-c:a", "aac", "-b:a", "192k",
            str(output_path),
        ]
    elif sfx == "flash":
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i",
            f"anoisesrc=c=white:d={duration:.3f}:r={sample_rate},"
            f"bandpass=f=3200:width_type=q:w=3.0,volume=4.5,afade=t=out:st=0.04:d={duration-0.04:.3f}",
            "-c:a", "aac", "-b:a", "192k",
            str(output_path),
        ]
    elif sfx == "glitch":
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i",
            f"aevalsrc=sin(2*PI*220*mod(t*30\\,1))*sin(2*PI*1200*t):d={duration:.3f}:s={sample_rate},"
            f"volume=3.0,afade=t=out:st={duration*0.5:.3f}:d={duration*0.5:.3f}",
            "-c:a", "aac", "-b:a", "192k",
            str(output_path),
        ]
    elif sfx == "thud":
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i",
            f"aevalsrc=sin(2*PI*75*t)*exp(-20*t):d={duration:.3f}:s={sample_rate},"
            f"volume=3.5",
            "-c:a", "aac", "-b:a", "192k",
            str(output_path),
        ]
    elif sfx == "paper":
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i",
            f"anoisesrc=c=pink:d={duration:.3f}:r={sample_rate},"
            f"bandpass=f=2800:width_type=q:w=2.0,volume=2.6,"
            f"afade=t=in:st=0:d=0.04,afade=t=out:st=0.08:d={max(0.05, duration-0.08):.3f}",
            "-c:a", "aac", "-b:a", "192k",
            str(output_path),
        ]
    else:  # riser
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i",
            f"anoisesrc=c=pink:d={duration:.3f}:r={sample_rate},"
            f"bandpass=f=800:width_type=q:w=2.0,volume=2.2,"
            f"afade=t=in:st=0:d={duration*0.6:.3f},afade=t=out:st={duration*0.6:.3f}:d={duration*0.4:.3f}",
            "-c:a", "aac", "-b:a", "192k",
            str(output_path),
        ]

    subprocess.run(cmd, check=True)
    return output_path


# ─────────────────────────────────────────────────────────────────────────────
# 3. Two-Clip Transition Applier (Between Clip A and Clip B)
# ─────────────────────────────────────────────────────────────────────────────

def apply_two_clip_transition(
    clip_a: Path,
    clip_b: Path,
    output_path: Path,
    transition_name: str = "whip_left",
    duration_sec: Optional[float] = None,
    with_sfx: bool = True,
) -> Path:
    """
    Seamlessly merge Clip A and Clip B using any Premiere Pro or CapCut transition,
    with audio crossfade and synchronized SFX.
    """
    clip_a = Path(clip_a)
    clip_b = Path(clip_b)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    t_info = get_transition_info(transition_name) or ALL_TRANSITIONS["whip_left"]
    t_dur = duration_sec or t_info.default_duration

    # Probe Clip A duration
    r_a = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(clip_a)
    ], capture_output=True, text=True, check=True)
    dur_a = float(json.loads(r_a.stdout).get("format", {}).get("duration", 5.0))
    offset = max(0.05, dur_a - t_dur)

    with tempfile.TemporaryDirectory(prefix="trans_2clip_") as tmp_dir:
        tmp_p = Path(tmp_dir)

        # 1. Custom expression transition or standard built-in xfade
        if t_info.custom_expr:
            v_filter = f"[0:v][1:v]xfade=transition=custom:duration={t_dur:.3f}:offset={offset:.3f}:expr='{t_info.custom_expr}'[v_out]"
            is_xfade = True
        elif t_info.xfade_type:
            v_filter = f"[0:v][1:v]xfade=transition={t_info.xfade_type}:duration={t_dur:.3f}:offset={offset:.3f}[v_out]"
            is_xfade = True
        else:
            is_xfade = False

        if is_xfade:
            a_filter = f"[0:a][1:a]acrossfade=d={t_dur:.3f}[a_out]"
            if with_sfx:
                sfx_file = tmp_p / "trans_sfx.m4a"
                generate_transition_sfx(t_info.sfx_type, sfx_file, duration=t_dur)
                sfx_delay_ms = int(offset * 1000)
                fc = (
                    f"{v_filter}; "
                    f"{a_filter}; "
                    f"[2:a]adelay={sfx_delay_ms}|{sfx_delay_ms},volume=0.85[sfx_delayed]; "
                    f"[a_out][sfx_delayed]amix=inputs=2:duration=first:weights=1.0 0.8[a_final]"
                )
                cmd = [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-i", str(clip_a),
                    "-i", str(clip_b),
                    "-i", str(sfx_file),
                    "-filter_complex", fc,
                    "-map", "[v_out]",
                    "-map", "[a_final]",
                    *get_h264_encoder_args(),
                    "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart",
                    str(output_path),
                ]
            else:
                cmd = [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-i", str(clip_a),
                    "-i", str(clip_b),
                    "-filter_complex", f"{v_filter}; {a_filter}",
                    "-map", "[v_out]",
                    "-map", "[a_out]",
                    *get_h264_encoder_args(),
                    "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart",
                    str(output_path),
                ]

            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0:
                cmd_sw = fallback_cmd_to_libx264(cmd)
                subprocess.run(cmd_sw, check=True)
        else:
            # Special effects (glitch, earthquake, vhs_damage)
            concat_tmp = tmp_p / "concat_raw.mp4"
            cmd_concat = [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-i", str(clip_a),
                "-i", str(clip_b),
                "-filter_complex", "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]",
                "-map", "[v]", "-map", "[a]",
                *get_h264_encoder_args(),
                "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k",
                str(concat_tmp),
            ]
            r = subprocess.run(cmd_concat, capture_output=True, text=True)
            if r.returncode != 0:
                cmd_sw = fallback_cmd_to_libx264(cmd_concat)
                subprocess.run(cmd_sw, check=True)

            apply_transition_pack_to_video(
                input_path=concat_tmp,
                output_path=output_path,
                pack_name=t_info.pack,
                cut_timestamps=[dur_a],
                with_sfx=with_sfx,
            )

    return output_path


# ─────────────────────────────────────────────────────────────────────────────
# 4. Multi-Cut Video Transition Pack Processor (Within a Single Video)
# ─────────────────────────────────────────────────────────────────────────────

def build_video_cut_transitions_filter(
    cut_timestamps: List[float],
    total_duration: float,
    transition_name: str = "whip_left",
    width: int = 1080,
    height: int = 1920,
) -> Tuple[str, List[str]]:
    """
    Build video filter expressions applying the chosen transition style
    at every cut boundary in a single video.
    Returns (video_filter_string, list_of_flash_conditions).
    """
    t_info = get_transition_info(transition_name) or ALL_TRANSITIONS["whip_left"]
    half_dur = t_info.default_duration / 2.0

    cuts = [c for c in cut_timestamps if 0.5 <= c <= total_duration - 0.5]
    v_filters = []
    flash_parts = []

    # 1. Whip / Slide / Push Movement Transitions
    if any(k in t_info.name for k in ["whip", "slide", "push", "split"]):
        whip_parts_x = []
        whip_parts_y = []
        whip_zoom_parts = []

        is_vertical = ("up" in t_info.name or "down" in t_info.name)
        sign = -1 if ("left" in t_info.name or "up" in t_info.name or "whip" == t_info.name) else 1

        for c in cuts:
            disp = 180 * sign
            if not is_vertical:
                whip_parts_x.append(
                    f"if(between(t,{c-half_dur:.2f},{c:.2f}),{disp}*(1-(({c:.2f}-t)/{half_dur:.2f})),"
                    f"if(between(t,{c:.2f},{c+half_dur:.2f}),{-disp}*(1-((t-{c:.2f})/{half_dur:.2f})),"
                )
            else:
                whip_parts_y.append(
                    f"if(between(t,{c-half_dur:.2f},{c:.2f}),{disp}*(1-(({c:.2f}-t)/{half_dur:.2f})),"
                    f"if(between(t,{c:.2f},{c+half_dur:.2f}),{-disp}*(1-((t-{c:.2f})/{half_dur:.2f})),"
                )
            whip_zoom_parts.append(f"between(t,{c-half_dur:.2f},{c+half_dur:.2f})")
            flash_parts.append(f"between(t,{c:.2f},{c+0.07:.2f})")

        whip_z_expr = f"if({'+'.join(whip_zoom_parts)}, 0.12, 0.0)" if whip_zoom_parts else "0.0"
        scale_w = f"2*trunc({width}*(1.0 + {whip_z_expr})/2)"
        scale_h = f"2*trunc({height}*(1.0 + {whip_z_expr})/2)"

        if whip_parts_x:
            nested_x = "".join(whip_parts_x) + "0" + (")" * len(whip_parts_x) * 2)
            crop_x = f"(iw-{width})/2 + {nested_x}"
        else:
            crop_x = f"(iw-{width})/2"

        if whip_parts_y:
            nested_y = "".join(whip_parts_y) + "0" + (")" * len(whip_parts_y) * 2)
            crop_y = f"(ih-{height})/2 + {nested_y}"
        else:
            crop_y = f"(ih-{height})/2"

        v_filters.append(f"scale='{scale_w}':'{scale_h}':eval=frame,crop={width}:{height}:'{crop_x}':'{crop_y}'")

    # 2. Punch Zoom & Cross Zoom
    elif "zoom" in t_info.name:
        z_parts = []
        for c in cuts:
            p_up, p_hold, p_back = 0.18, 0.45, 0.40
            z_expr = (
                f"if(between(t,{c:.2f},{c+p_up:.2f}),(1.0+0.25*(t-{c:.2f})/{p_up:.2f}),"
                f"if(between(t,{c+p_up:.2f},{c+p_up+p_hold:.2f}),1.25,"
                f"if(between(t,{c+p_up+p_hold:.2f},{c+p_up+p_hold+p_back:.2f}),(1.25-0.25*(t-{c+p_up+p_hold:.2f})/{p_back:.2f}),1.0)))"
            )
            z_parts.append(f"if(between(t,{c:.2f},{c+p_up+p_hold+p_back:.2f}),{z_expr},")

        nested_z = "".join(z_parts) + "1.0" + (")" * len(z_parts)) if z_parts else "1.0"
        scale_w = f"2*trunc({width}*{nested_z}/2)"
        scale_h = f"2*trunc({height}*{nested_z}/2)"
        crop_x = f"(iw-{width})/2"
        crop_y = f"(ih-{height})/2"
        v_filters.append(f"scale='{scale_w}':'{scale_h}':eval=frame,crop={width}:{height}:'{crop_x}':'{crop_y}'")

    # 3. Earthquake & Impact Camera Shake
    elif "shake" in t_info.name or "earthquake" in t_info.name:
        shake_x_parts = []
        shake_y_parts = []
        for c in cuts:
            shake_x_parts.append(
                f"if(between(t,{c:.2f},{c+0.35:.2f}),38*sin(65*(t-{c:.2f}))*exp(-6*(t-{c:.2f})),"
            )
            shake_y_parts.append(
                f"if(between(t,{c:.2f},{c+0.35:.2f}),28*cos(55*(t-{c:.2f}))*exp(-6*(t-{c:.2f})),"
            )
            flash_parts.append(f"between(t,{c:.2f},{c+0.06:.2f})")

        scale_w = f"2*trunc({width}*1.12/2)"
        scale_h = f"2*trunc({height}*1.12/2)"
        nested_sx = "".join(shake_x_parts) + "0" + (")" * len(shake_x_parts)) if shake_x_parts else "0"
        nested_sy = "".join(shake_y_parts) + "0" + (")" * len(shake_y_parts)) if shake_y_parts else "0"
        crop_x = f"(iw-{width})/2 + {nested_sx}"
        crop_y = f"(ih-{height})/2 + {nested_sy}"
        v_filters.append(f"scale='{scale_w}':'{scale_h}':eval=frame,crop={width}:{height}:'{crop_x}':'{crop_y}'")

    # 4. Glitch / VHS Damage
    elif "glitch" in t_info.name or "vhs" in t_info.name:
        glitch_parts = []
        for c in cuts:
            glitch_parts.append(f"between(t,{c:.2f},{c+0.20:.2f})")
            flash_parts.append(f"between(t,{c:.2f},{c+0.05:.2f})")
        v_filters.append(f"scale={width}:{height}")
        if glitch_parts:
            g_test = "+".join(glitch_parts)
            v_filters.append(f"noise=alls=15:allf=t+u:enable='{g_test}'")

    # 5. Optical Flash / Dip to White
    elif "flash" in t_info.name or "white" in t_info.name:
        for c in cuts:
            flash_parts.append(f"between(t,{c:.2f},{c+0.12:.2f})")
        v_filters.append(f"scale={width}:{height}")

    # Fallback default
    else:
        v_filters.append(f"scale={width}:{height}")
        for c in cuts:
            flash_parts.append(f"between(t,{c:.2f},{c+0.06:.2f})")

    # Optical White Flash at cut midpoints
    if flash_parts:
        test = "+".join(flash_parts)
        v_filters.append(f"eq=brightness='if({test}, 0.55, 0.0)':eval=frame")

    return ",".join(v_filters), flash_parts


def apply_transition_pack_to_video(
    input_path: Path,
    output_path: Path,
    pack_name: str = "premiere_pro_all",
    cut_timestamps: Optional[List[float]] = None,
    with_sfx: bool = True,
) -> Path:
    """
    Apply an entire Premiere Pro or CapCut transition pack across an entire video.
    Detects scene cuts automatically if cut_timestamps is not provided.
    """
    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Probe resolution & duration
    r_probe = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration:stream=width,height", "-of", "json", str(input_path)
    ], capture_output=True, text=True, check=True)
    info = json.loads(r_probe.stdout)
    v_stream = next((s for s in info.get("streams", []) if s.get("width")), {})
    width = int(v_stream.get("width", 1080))
    height = int(v_stream.get("height", 1920))
    duration = float(info.get("format", {}).get("duration", 10.0))

    # Detect cuts if not passed
    if cut_timestamps is None:
        from .scene_detector import detect_camera_cuts
        cut_timestamps = detect_camera_cuts(input_path, adaptive_threshold=2.8, min_scene_len_sec=0.7)

    cuts = [c for c in cut_timestamps if 0.5 <= c <= duration - 0.5]
    print(f"🎬 Applying '{pack_name}' transition pack on {len(cuts)} shot boundaries …")

    pack_transitions = TRANSITION_PACKS.get(pack_name, TRANSITION_PACKS["premiere_pro_all"])
    primary_trans = pack_transitions[0]

    with tempfile.TemporaryDirectory(prefix="trans_pack_") as tmp_dir:
        tmp_p = Path(tmp_dir)

        # 1. Build visual filter chain
        v_filters, _ = build_video_cut_transitions_filter(cuts, duration, primary_trans, width, height)

        # 2. Build multi-cut SFX track
        if with_sfx and cuts:
            fc_sfx = [f"anullsrc=r=48000:cl=mono,atrim=0:{duration:.3f}[base]"]
            mix_inputs = ["[base]"]

            # Opening hook boom
            fc_sfx.append("aevalsrc=sin(2*PI*55*exp(-4.5*t)):d=0.55,lowpass=f=130,volume=2.2[boom0]")
            mix_inputs.append("[boom0]")

            for idx, c in enumerate(cuts[:25]):
                tag = f"sfx_{idx}"
                delay_ms = int(max(0, c - 0.10) * 1000)
                fc_sfx.append(
                    f"anoisesrc=c=pink:d=0.22,bandpass=f=1200:width_type=q:w=2.4,volume=2.8,"
                    f"afade=t=in:st=0:d=0.06,afade=t=out:st=0.10:d=0.12,"
                    f"adelay={delay_ms}|{delay_ms}[{tag}]"
                )
                mix_inputs.append(f"[{tag}]")

            fc_sfx.append(
                f"{''.join(mix_inputs)}amix=inputs={len(mix_inputs)}:normalize=0:dropout_transition=0,"
                f"loudnorm=I=-16:TP=-1.5:LRA=10[sfx_out]"
            )

            sfx_file = tmp_p / "pack_sfx.m4a"
            cmd_sfx = [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-filter_complex", ";".join(fc_sfx),
                "-map", "[sfx_out]",
                "-c:a", "aac", "-b:a", "192k",
                str(sfx_file),
            ]
            subprocess.run(cmd_sfx, check=True)

            cmd = [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-i", str(input_path),
                "-i", str(sfx_file),
                "-filter_complex",
                f"[0:v]{v_filters}[v_out]; "
                f"[0:a][1:a]amix=inputs=2:duration=first:weights=1.0 0.85[a_mix]; "
                f"[a_mix]highpass=f=75,loudnorm=I=-14:TP=-1.0:LRA=9,alimiter=limit=-1.0dB[a_out]",
                "-map", "[v_out]",
                "-map", "[a_out]",
                *get_h264_encoder_args(),
                "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart",
                str(output_path),
            ]
        else:
            cmd = [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-i", str(input_path),
                "-filter_complex", f"[0:v]{v_filters}[v_out]",
                "-map", "[v_out]",
                "-map", "0:a?",
                *get_h264_encoder_args(),
                "-pix_fmt", "yuv420p",
                "-c:a", "copy",
                "-movflags", "+faststart",
                str(output_path),
            ]

        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            cmd_sw = fallback_cmd_to_libx264(cmd)
            subprocess.run(cmd_sw, check=True)

    print(f"✅ Transition Pack applied -> {output_path.name}")
    return output_path
