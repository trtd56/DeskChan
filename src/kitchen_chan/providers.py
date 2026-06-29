from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .prompts import system_prompt_for_scene
from .schemas import response_schema_for_scene


@dataclass(frozen=True)
class ModelResult:
    provider: str
    model: str
    latency_ms: int
    data: dict[str, Any]
    raw_timing: dict[str, Any]


class GameProvider(Protocol):
    provider: str
    model: str

    def complete(
        self,
        user_text: str,
        image_path: Path | None = None,
        *,
        scene: str = "tetris",
    ) -> ModelResult:
        """Return a structured Tetris commentary response."""


class MockProvider:
    provider = "mock"
    model = "mock-tetrischan"

    def complete(
        self,
        user_text: str,
        image_path: Path | None = None,
        *,
        scene: str = "tetris",
    ) -> ModelResult:
        started = time.perf_counter()
        prompt_text = user_text.split("\n\nテトリス実況", 1)[0]
        prompt_text = prompt_text.split("\n\n卓上実況", 1)[0]
        prompt_text = prompt_text.split("\n\n自動デモ", 1)[0]
        lowered = prompt_text.lower()
        if scene == "desk":
            data = _mock_desk_response(lowered)
            latency_ms = int((time.perf_counter() - started) * 1000)
            return ModelResult(self.provider, "mock-deskchan", latency_ms, data, {"mock": True})

        if any(word in lowered for word in ["デモ", "demo", "紹介"]):
            audio_key = "tetris_demo_intro"
            safety_level = "ok"
            reply = "こちら、盤面ツッコミ搭載StackChanです。積み方の迷子、見逃さへんで。"
            phase = "menu"
        elif any(word in lowered for word in ["遅い", "速度", "latency", "speed"]):
            audio_key = "tetris_demo_latency_joke"
            safety_level = "ok"
            reply = "返事が遅いと、次のミノ来てから後悔するんよ。実況は速度が命やで。"
            phase = "unknown"
        elif any(word in lowered for word in ["雑談", "しゃべ", "暇", "待って", "wait"]):
            audio_key = "tetris_wait_piece"
            safety_level = "ok"
            reply = "次のミノ待ちやな。ここで心拍上げたら、指だけ暴走するで。"
            phase = "spawn"
        elif any(word in lowered for word in ["うま", "成功", "nice", "いい"]):
            audio_key = "tetris_nice_place"
            safety_level = "ok"
            reply = "ええ置き方やん。今の一手、盤面がちょっと礼儀正しくなったで。"
            phase = "stacking"
        elif any(word in lowered for word in ["ミス", "misdrop", "置きミス", "失敗", "failed"]):
            audio_key = "tetris_misdrop"
            safety_level = "ok"
            reply = "置きミスやな。まだ終わりちゃう、右の穴をふさいで立て直そ。"
            phase = "defense"
        elif any(word in lowered for word in ["ゲームオーバー", "top out", "トップアウト", "負け"]):
            audio_key = "tetris_game_over_react"
            safety_level = "stop"
            reply = "トップアウトや。今のは盤面が天井に挨拶しに行ってもうたな。"
            phase = "top_out"
        elif any(
            word in lowered
            for word in ["危", "高い", "高く", "高め", "詰", "埋ま", "danger", "やば", "ピンチ"]
        ):
            audio_key = "tetris_danger_high_stack"
            safety_level = "warn"
            reply = "積み上がりすぎや。消せる列を優先して、Tetris欲張りはいったん封印や。"
            phase = "danger"
        elif any(word in lowered for word in ["写真", "画像", "photo", "camera"]):
            audio_key = "tetris_board_check"
            safety_level = "ok"
            reply = "盤面見るで。ネクストとホールドも入れてくれたら、ツッコミ精度上がるわ。"
            phase = "unknown"
        elif any(word in lowered for word in ["暗", "dark"]):
            audio_key = "tetris_photo_too_dark"
            safety_level = "stop"
            reply = "画面暗いな。これやとIミノか影か分からん。明るさ上げてもう一回や。"
            phase = "unknown"
        elif any(word in lowered for word in ["ブレ", "ぼけ", "blurry"]):
            audio_key = "tetris_photo_blurry"
            safety_level = "stop"
            reply = "ブレてるで。盤面が高速落下しすぎや。固定して撮り直そか。"
            phase = "unknown"
        elif any(word in lowered for word in ["hold", "ホールド", "入れ替"]):
            audio_key = "tetris_hold_now"
            safety_level = "ok"
            reply = "ここはホールドや。今のミノで無理するより、次で形を整えよ。"
            phase = "defense"
        elif any(word in lowered for word in ["tetris", "テトリス", "4ライン", "四列", "iミノ", "アイミノ"]):
            audio_key = "tetris_ready_tetris"
            safety_level = "ok"
            reply = "右端の井戸、空いてるやん。Iミノ来たら一気に気持ちええやつや。"
            phase = "attack"
        elif any(word in lowered for word in ["t-spin", "tspin", "tスピン", "ティースピン"]):
            audio_key = "tetris_tspin_setup"
            safety_level = "ok"
            reply = "Tスピンの匂いするな。穴をふさがず、屋根だけ丁寧に作ろか。"
            phase = "attack"
        elif any(word in lowered for word in ["garbage", "おじゃま", "攻撃"]):
            audio_key = "tetris_garbage_incoming"
            safety_level = "warn"
            reply = "おじゃま来てるで。火力より生存優先、消せる列から片付けよ。"
            phase = "defense"
        elif any(word in lowered for word in ["combo", "コンボ", "ren", "連"]):
            audio_key = "tetris_combo_keep"
            safety_level = "ok"
            reply = "コンボ続いてるで。欲張りすぎず、次も一列消しでつなげよ。"
            phase = "attack"
        elif any(word in lowered for word in ["右", "right"]):
            audio_key = "tetris_move_right"
            safety_level = "ok"
            reply = "右へ寄せよか。井戸を埋めたら、あとで自分に怒られるで。"
            phase = "stacking"
        elif any(word in lowered for word in ["左", "left"]):
            audio_key = "tetris_move_left"
            safety_level = "ok"
            reply = "左へ寄せて平らにしよ。右の井戸はVIP席や、空けとき。"
            phase = "stacking"
        elif any(word in lowered for word in ["回転", "rotate", "spin"]):
            audio_key = "tetris_rotate_cw"
            safety_level = "ok"
            reply = "一回転させてから置こ。今の角度やと、盤面に迷惑かけるで。"
            phase = "stacking"
        elif any(word in lowered for word in ["消", "clear", "ライン"]):
            audio_key = "tetris_double_clear"
            safety_level = "ok"
            reply = "ライン消し優先や。派手さより、今は足場の掃除が大事やで。"
            phase = "clear"
        elif any(word in lowered for word in ["次", "ネクスト", "next"]):
            audio_key = "tetris_next_piece"
            safety_level = "ok"
            reply = "次ミノまで見て置こ。今だけ良くても、二手先で泣くやつや。"
            phase = "spawn"
        else:
            audio_key = "tetris_keep_well_open"
            safety_level = "ok"
            reply = "右端の井戸は空けとこ。そこ埋めたら、未来の自分から苦情くるで。"
            phase = "stacking"

        data = {
            "reply": reply,
            "safety_level": safety_level,
            "game_phase": phase,
            "stackchan": {
                "expression": "serious" if safety_level != "ok" else "happy",
                "motion": "nod",
                "audio_key": audio_key,
                "intensity": 2,
            },
            "actions": [reply],
            "timers": [],
            "visual_checklist": ["盤面の高さ", "右端の井戸", "ホールド", "ネクスト"],
            "agent_notes": [
                {"agent": "vision", "vote": "テトリス盤面として解釈"},
                {"agent": "strategy", "vote": phase},
                {"agent": "banter", "vote": audio_key},
            ],
            "demo_caption": "StackChanが盤面を見て、実況と次の一手を即答します。",
        }
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
        *,
        scene: str = "tetris",
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
                system_instruction=system_prompt_for_scene(scene),
                response_mime_type="application/json",
                response_json_schema=response_schema_for_scene(scene),
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


class CerebrasGemmaProvider:
    provider = "cerebras"

    def __init__(self) -> None:
        self.model = os.getenv("CEREBRAS_MODEL", "gemma-4-31b")

    def complete(
        self,
        user_text: str,
        image_path: Path | None = None,
        *,
        scene: str = "tetris",
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
                {"role": "system", "content": system_prompt_for_scene(scene)},
                {"role": "user", "content": user_content},
            ],
            reasoning_effort=os.getenv("CEREBRAS_REASONING_EFFORT", "none"),
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "game_response",
                    "strict": True,
                    "schema": _schema_for_cerebras(response_schema_for_scene(scene)),
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


def get_provider(name: str) -> GameProvider:
    normalized = name.lower()
    if normalized == "mock":
        return MockProvider()
    if normalized in {"gemini", "flash-lite", "gemini-flash-lite"}:
        return GeminiFlashLiteProvider()
    if normalized in {"cerebras", "gemma", "gemma-4"}:
        return CerebrasGemmaProvider()
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
        reply = "こちら卓上実況StackChanです。仕事も休憩も、机の上から見守るで。"
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
        phase = "focused_work"
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
        reply = "お、仕事始めたな。今日もコード書くんか、がんばれよ。"
        phase = "work_start"

    return {
        "reply": reply,
        "safety_level": safety_level,
        "game_phase": phase,
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
        "demo_caption": "StackChanが机上の変化を見て、短く実況や注意を返します。",
    }
