from __future__ import annotations

import json
from pathlib import Path
from typing import Any


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

DEFAULT_VOICE_KEYS = {
    "desk_beat_cup_watch",
    "desk_beat_focus",
    "desk_beat_phone_watch",
    "desk_beat_typing",
    "desk_beat_working",
    "desk_camera_blurry",
    "desk_chitchat_low_latency",
    "desk_chitchat_stackchan",
    "desk_chitchat_watchful",
    "desk_clutter_warning",
    "desk_cup_danger_1",
    "desk_cup_danger_2",
    "desk_cup_danger_3",
    "desk_demo_final_line",
    "desk_demo_intro",
    "desk_focus_achieved_1",
    "desk_focus_achieved_2",
    "desk_focus_achieved_3",
    "desk_focus_good",
    "desk_focus_one_hour",
    "desk_greeting_1",
    "desk_greeting_2",
    "desk_greeting_3",
    "desk_hand_between_cup_keyboard",
    "desk_hydration",
    "desk_leave_seat",
    "desk_lighting_dark",
    "desk_mug_near_edge",
    "desk_mug_near_pc",
    "desk_phone_overuse_1",
    "desk_phone_overuse_2",
    "desk_phone_overuse_3",
    "desk_phone_pickup",
    "desk_phone_pickup_1",
    "desk_phone_pickup_2",
    "desk_phone_pickup_3",
    "desk_phone_too_long",
    "desk_posture_long_still",
    "desk_repeated_motion",
    "desk_silence_focus",
    "desk_typing_fast",
    "desk_typing_fast_1",
    "desk_typing_fast_2",
    "desk_typing_fast_3",
    "desk_typing_stopped",
    "desk_unknown_scene",
    "desk_work_start",
    "desk_work_start_1",
    "desk_work_start_2",
    "desk_work_start_3",
    "desk_yawn",
    "desk_yawn_1",
    "desk_yawn_2",
    "desk_yawn_3",
}


def _load_voice_keys() -> set[str]:
    voice_path = Path(__file__).resolve().parents[2] / "data" / "desk_voice_lines.json"
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


DESK_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "reply": {
            "type": "string",
            "description": "One short Japanese desk-work line for StackChan.",
        },
        "safety_level": {
            "type": "string",
            "enum": ["ok", "warn", "stop"],
            "description": "warn is for spill, posture, distraction, lighting, or clutter concerns; stop is for unreadable state.",
        },
        "desk_phase": {
            "type": "string",
            "enum": DESK_PHASES,
            "description": "Current visible desk-work state.",
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
                    "enum": sorted(_load_voice_keys()),
                    "description": "Key from data/desk_voice_lines.json.",
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
            "description": "A short caption for UI display.",
        },
    },
    "required": [
        "reply",
        "safety_level",
        "desk_phase",
        "stackchan",
        "actions",
        "timers",
        "visual_checklist",
        "agent_notes",
        "demo_caption",
    ],
}


def response_schema() -> dict[str, Any]:
    return DESK_RESPONSE_SCHEMA
