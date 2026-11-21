# engine/__init__.py
from .encoder_utils import (
    get_h264_encoder_args,
    get_h264_encoder_name,
    fallback_cmd_to_libx264,
)
from .clipper_engine import (
    ViralityScore,
    ClipCandidate,
    score_highlights,
    build_virality_prompt,
    _snap_to_word_boundary,
)
from .viral_subtitles import (
    burn_viral_subtitles,
    get_style_preset,
    SubtitleStyle,
)
from .viral_editor import (
    assemble_viral_clip,
    add_hook_banner_to_video,
    reframe_video_9_16,
    render_hook_banner_image,
)
from .viral_enhancer import (
    apply_viral_master_suite,
    build_viral_visual_filters,
    build_dynamic_motion_zoom_filter,
    build_white_flash_filter,
    generate_viral_sfx,
)
from .transition_pack import (
    ALL_TRANSITIONS,
    TRANSITION_PACKS,
    TransitionInfo,
    apply_two_clip_transition,
    apply_transition_pack_to_video,
    generate_transition_sfx,
    get_available_packs,
    get_transition_info,
)
from .transition_director import (
    TransitionDirector,
    EditorialPlan,
)
from .face_tracker import (
    SotaFaceTracker,
    get_face_centered_crop_filter,
)
from .scene_detector import (
    detect_camera_cuts,
    snap_to_camera_cut,
    refine_clip_boundaries_with_scenes,
)
from .gta6_clipping import (
    GTA6_MOMENTS,
    GTA6MomentConfig,
    classify_gta6_moment,
    gameplay_facecam_stack,
    detect_cutscene_spoiler,
    render_music_safe_variant,
    format_gta6_clip_filename,
)

snap_to_boundaries = _snap_to_word_boundary

__all__ = [
    "get_h264_encoder_args",
    "get_h264_encoder_name",
    "fallback_cmd_to_libx264",
    "ViralityScore",
    "ClipCandidate",
    "score_highlights",
    "build_virality_prompt",
    "snap_to_boundaries",
    "_snap_to_word_boundary",
    "burn_viral_subtitles",
    "get_style_preset",
    "SubtitleStyle",
    "assemble_viral_clip",
    "add_hook_banner_to_video",
    "reframe_video_9_16",
    "render_hook_banner_image",
    "apply_viral_master_suite",
    "build_viral_visual_filters",
    "generate_viral_sfx",
    "SotaFaceTracker",
    "get_face_centered_crop_filter",
    "detect_camera_cuts",
    "snap_to_camera_cut",
    "refine_clip_boundaries_with_scenes",
    "GTA6_MOMENTS",
    "GTA6MomentConfig",
    "classify_gta6_moment",
    "gameplay_facecam_stack",
    "detect_cutscene_spoiler",
    "render_music_safe_variant",
    "format_gta6_clip_filename",
    "ALL_TRANSITIONS",
    "TRANSITION_PACKS",
    "TransitionInfo",
    "apply_two_clip_transition",
    "apply_transition_pack_to_video",
    "generate_transition_sfx",
    "get_available_packs",
    "get_transition_info",
    "TransitionDirector",
    "EditorialPlan",
]

