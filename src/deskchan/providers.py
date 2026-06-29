from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .prompts import system_prompt
from .schemas import response_schema


@dataclass(frozen=True)
class ModelResult:
    provider: str
    model: str
    latency_ms: int
    data: dict[str, Any]
    raw_timing: dict[str, Any]


class DeskProvider(Protocol):
    provider: str
    model: str

    def complete(
        self,
        user_text: str,
        image_path: Path | None = None,
    ) -> ModelResult:
        """Return a structured DeskChan response."""


class MockProvider:
    provider = "mock"
    model = "mock-deskchan"

    def complete(
        self,
        user_text: str,
        image_path: Path | None = None,
    ) -> ModelResult:
        started = time.perf_counter()
        prompt_text = user_text.split("\n\n卓上", 1)[0]
        prompt_text = prompt_text.split("\n\n自動", 1)[0]
        data = _mock_desk_response(prompt_text.lower())
        latency_ms = int((time.perf_counter() - started) * 1000)
        return ModelResult(self.provider, self.model, latency_ms, data, {"mock": True})


class GeminiFlashLiteProvider:
    provider = "gemini"

    def __init__(self) -> None:
        self.model = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

    def complete(
        self,
        user_text: str,
        image_path: Path | None = None,
    ) -> ModelResult:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        contents: list[Any] = [user_text]
        if image_path:
            contents.append(
                types.Part.from_bytes(
                    data=image_path.read_bytes(),
                    mime_type=_mime_type(image_path),
                )
            )

        started = time.perf_counter()
        response = client.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt(),
                response_mime_type="application/json",
                response_json_schema=response_schema(),
            ),
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        return ModelResult(
            self.provider,
            self.model,
            latency_ms,
            json.loads(response.text),
            {"sdk_latency_ms": latency_ms},
        )


class CerebrasProvider:
    provider = "cerebras"

    def __init__(self) -> None:
        self.model = os.getenv("CEREBRAS_MODEL", "gemma-4-31b")

    def complete(
        self,
        user_text: str,
        image_path: Path | None = None,
    ) -> ModelResult:
        from openai import OpenAI

        api_key = os.getenv("CEREBRAS_API_KEY")
        if not api_key:
            raise ValueError("CEREBRAS_API_KEY is not set.")

        user_content: str | list[dict[str, Any]] = user_text
        if image_path:
            user_content = [
                {"type": "text", "text": user_text},
                {"type": "image_url", "image_url": {"url": _image_data_uri(image_path)}},
            ]

        client = OpenAI(
            api_key=api_key,
            base_url=os.getenv("CEREBRAS_BASE_URL", "https://api.cerebras.ai/v1"),
        )
        started = time.perf_counter()
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt()},
                {"role": "user", "content": user_content},
            ],
            reasoning_effort=os.getenv("CEREBRAS_REASONING_EFFORT", "none"),
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "desk_response",
                    "strict": True,
                    "schema": _schema_for_cerebras(response_schema()),
                },
            },
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        content = response.choices[0].message.content or "{}"
        raw_timing = getattr(response, "time_info", None)
        return ModelResult(
            self.provider,
            self.model,
            latency_ms,
            json.loads(content),
            raw_timing if isinstance(raw_timing, dict) else {"sdk_latency_ms": latency_ms},
        )


def get_provider(name: str) -> DeskProvider:
    normalized = name.lower()
    if normalized == "mock":
        return MockProvider()
    if normalized in {"gemini", "flash-lite", "gemini-flash-lite"}:
        return GeminiFlashLiteProvider()
    if normalized in {"cerebras", "gemma", "gemma-4"}:
        return CerebrasProvider()
    raise ValueError(f"Unknown provider: {name}")


def _mime_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if suffix == ".webp":
        return "image/webp"
    raise ValueError(f"Unsupported image type: {path.suffix}")


def _image_data_uri(path: Path) -> str:
    mime_type = _mime_type(path)
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _schema_for_cerebras(schema: dict[str, Any]) -> dict[str, Any]:
    copied = json.loads(json.dumps(schema))
    _drop_schema_keys(copied, {"minItems", "maxItems"})
    return copied


def _drop_schema_keys(value: Any, keys: set[str]) -> None:
    if isinstance(value, dict):
        for key in keys:
            value.pop(key, None)
        for child in value.values():
            _drop_schema_keys(child, keys)
    elif isinstance(value, list):
        for child in value:
            _drop_schema_keys(child, keys)


def _mock_desk_response(lowered: str) -> dict[str, Any]:
    if any(word in lowered for word in ["デモ", "demo", "紹介"]):
        audio_key = "desk_demo_intro"
        safety_level = "ok"
        reply = "こちらDeskChanです。机の上から、作業を見守るで。"
        phase = "idle"
    elif any(word in lowered for word in ["カップ", "マグ", "こぼ", "端", "cup", "mug"]):
        audio_key = "desk_mug_near_edge"
        safety_level = "warn"
        reply = "あ、マグカップ危ないって。こぼれるこぼれる。"
        phase = "desk_risk"
    elif any(word in lowered for word in ["スマホ", "phone"]):
        audio_key = "desk_phone_pickup"
        safety_level = "ok"
        reply = "お、スマホ触ったな。5分で戻ってこいよ。"
        phase = "phone"
    elif any(word in lowered for word in ["長い", "long", "40分", "姿勢", "動いて"]):
        audio_key = "desk_posture_long_still"
        safety_level = "warn"
        reply = "もう40分動いてへんで。ちょっと伸びしようや。"
        phase = "focused_work"
    elif any(word in lowered for word in ["速", "typing", "タイピング"]):
        audio_key = "desk_typing_fast"
        safety_level = "ok"
        reply = "お、ノってきたやん。今めっちゃ速いで。"
        phase = "typing_fast"
    elif any(word in lowered for word in ["止ま", "詰ま", "stuck"]):
        audio_key = "desk_typing_stopped"
        safety_level = "ok"
        reply = "止まったな。詰まっとる顔やそれ。"
        phase = "stuck"
    elif any(word in lowered for word in ["飲", "水", "給水", "drink"]):
        audio_key = "desk_hydration"
        safety_level = "ok"
        reply = "給水ナイス。水分大事やからな。"
        phase = "hydration"
    elif any(word in lowered for word in ["暗", "lighting", "dark"]):
        audio_key = "desk_lighting_dark"
        safety_level = "warn"
        reply = "暗いて。目悪なるで、電気つけ。"
        phase = "lighting"
    elif any(word in lowered for word in ["散ら", "片付", "clutter"]):
        audio_key = "desk_clutter_warning"
        safety_level = "warn"
        reply = "机ぐちゃぐちゃやん。一回片付けたら？"
        phase = "cleanup"
    else:
        audio_key = "desk_work_start"
        safety_level = "ok"
        reply = "お、仕事始めたな。今日もがんばれよ。"
        phase = "work_start"

    return {
        "reply": reply,
        "safety_level": safety_level,
        "desk_phase": phase,
        "stackchan": {
            "expression": "serious" if safety_level != "ok" else "happy",
            "motion": "nod",
            "audio_key": audio_key,
            "intensity": 2,
        },
        "actions": [reply],
        "timers": [],
        "visual_checklist": ["手元", "キーボード", "カップ", "スマホ"],
        "agent_notes": [
            {"agent": "vision", "vote": "卓上作業として解釈"},
            {"agent": "strategy", "vote": phase},
            {"agent": "banter", "vote": audio_key},
        ],
        "demo_caption": "DeskChanが机上の変化を見て、短くコメントします。",
    }
