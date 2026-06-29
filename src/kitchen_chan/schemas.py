from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SCENE_VOICE_FILES = {
    "tetris": "tetris_voice_lines.json",
    "desk": "desk_voice_lines.json",
}

TETRIS_PHASES = [
    "menu",
    "spawn",
    "stacking",
    "attack",
    "defense",
    "danger",
    "clear",
    "top_out",
    "unknown",
]

DESK_PHASES = [
    "idle",
    "greeting",
    "work_start",
    "focused_work",
    "typing_fast",
    "stuck",
    "break",
    "hydration",
    "phone",
    "phone_pickup",
    "phone_overuse",
    "desk_risk",
    "cup_danger",
    "cleanup",
    "lighting",
    "yawn",
    "focus_achieved",
    "unknown",
]


GAME_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "reply": {
            "type": "string",
            "description": "One short Japanese Tetris commentary line for StackChan.",
        },
        "safety_level": {
            "type": "string",
            "enum": ["ok", "warn", "stop"],
            "description": "warn is for high stack or incoming garbage; stop is for top out or unreadable state.",
        },
        "game_phase": {
            "type": "string",
            "enum": [
                "menu",
                "spawn",
                "stacking",
                "attack",
                "defense",
                "danger",
                "clear",
                "top_out",
                "unknown",
            ],
        },
        "stackchan": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "expression": {
                    "type": "string",
                    "enum": ["neutral", "happy", "serious", "surprised", "angry", "sleepy"],
                },
                "motion": {
                    "type": "string",
                    "enum": ["none", "nod", "shake", "tilt_left", "tilt_right", "bounce"],
                },
                "audio_key": {
                    "type": "string",
                    "description": "Key from data/tetris_voice_lines.json.",
                },
                "intensity": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 3,
                },
            },
            "required": ["expression", "motion", "audio_key", "intensity"],
        },
        "actions": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 4,
        },
        "timers": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "label": {"type": "string"},
                    "seconds": {"type": "integer", "minimum": 1, "maximum": 7200},
                },
                "required": ["label", "seconds"],
            },
            "maxItems": 3,
        },
        "visual_checklist": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 4,
        },
        "agent_notes": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "agent": {"type": "string", "enum": ["vision", "strategy", "banter"]},
                    "vote": {"type": "string"},
                },
                "required": ["agent", "vote"],
            },
            "minItems": 3,
            "maxItems": 3,
        },
        "demo_caption": {
            "type": "string",
            "description": "A short caption that explains the UX value for a demo overlay.",
        },
    },
    "required": [
        "reply",
        "safety_level",
        "game_phase",
        "stackchan",
        "actions",
        "timers",
        "visual_checklist",
        "agent_notes",
        "demo_caption",
    ],
}

DESK_RESPONSE_SCHEMA = json.loads(json.dumps(GAME_RESPONSE_SCHEMA))
DESK_RESPONSE_SCHEMA["properties"]["reply"][
    "description"
] = "One short Japanese desk-work commentary line for StackChan."
DESK_RESPONSE_SCHEMA["properties"]["safety_level"][
    "description"
] = "warn is for spill, posture, distraction, lighting, or clutter concerns; stop is for unreadable state."
DESK_RESPONSE_SCHEMA["properties"]["game_phase"]["enum"] = DESK_PHASES
DESK_RESPONSE_SCHEMA["properties"]["stackchan"]["properties"]["audio_key"][
    "description"
] = "Key from data/desk_voice_lines.json."

GAME_RESPONSE_SCHEMA["properties"]["game_phase"]["enum"] = TETRIS_PHASES


DEFAULT_VOICE_KEYS = {
    "tetris_board_check",
    "tetris_build_flat",
    "tetris_chitchat_camera",
    "tetris_chitchat_commentary",
    "tetris_chitchat_speed",
    "tetris_chitchat_stackchan",
    "tetris_close_call",
    "tetris_combo_keep",
    "tetris_combo_start",
    "tetris_danger_high_stack",
    "tetris_demo_compare",
    "tetris_demo_final_line",
    "tetris_demo_intro",
    "tetris_demo_latency_joke",
    "tetris_double_clear",
    "tetris_game_over_react",
    "tetris_garbage_incoming",
    "tetris_hard_drop",
    "tetris_hold_now",
    "tetris_keep_well_open",
    "tetris_misdrop",
    "tetris_move_left",
    "tetris_move_right",
    "tetris_next_piece",
    "tetris_nice_place",
    "tetris_panic_stop",
    "tetris_photo_blurry",
    "tetris_photo_too_dark",
    "tetris_ready_tetris",
    "tetris_recover",
    "tetris_rotate_ccw",
    "tetris_rotate_cw",
    "tetris_save_hold",
    "tetris_single_clear",
    "tetris_soft_drop",
    "tetris_stack_left",
    "tetris_stack_right",
    "tetris_start_watch",
    "tetris_tetris_clear",
    "tetris_tspin_clear",
    "tetris_tspin_setup",
    "tetris_unknown_board",
    "tetris_wait_lock",
    "tetris_wait_opponent",
    "tetris_wait_piece",
    "tetris_well_blocked_warn",
}


def _load_voice_keys(scene: str) -> set[str]:
    filename = SCENE_VOICE_FILES.get(scene, SCENE_VOICE_FILES["tetris"])
    voice_path = Path(__file__).resolve().parents[2] / "data" / filename
    if not voice_path.exists():
        return DEFAULT_VOICE_KEYS
    try:
        payload = json.loads(voice_path.read_text(encoding="utf-8"))
    except Exception:
        return DEFAULT_VOICE_KEYS
    keys = {
        str(item["key"])
        for item in payload
        if isinstance(item, dict) and isinstance(item.get("key"), str)
    }
    return keys or DEFAULT_VOICE_KEYS


VOICE_KEYS = _load_voice_keys("tetris")
GAME_RESPONSE_SCHEMA["properties"]["stackchan"]["properties"]["audio_key"]["enum"] = sorted(VOICE_KEYS)

DESK_VOICE_KEYS = _load_voice_keys("desk")
DESK_RESPONSE_SCHEMA["properties"]["stackchan"]["properties"]["audio_key"]["enum"] = sorted(DESK_VOICE_KEYS)


def response_schema_for_scene(scene: str) -> dict[str, Any]:
    if scene == "desk":
        return DESK_RESPONSE_SCHEMA
    return GAME_RESPONSE_SCHEMA

COOKING_RESPONSE_SCHEMA = GAME_RESPONSE_SCHEMA
