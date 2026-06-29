from __future__ import annotations

import argparse
import json
import mimetypes
import os
import time
import urllib.request
import wave
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv

from .providers import get_provider
from .stackchan import capture_snapshot, post_action, to_action_packet


DESK_WAIT_KEYS = [
    "desk_beat_working",
    "desk_beat_typing",
    "desk_beat_focus",
    "desk_focus_good",
    "desk_silence_focus",
]

DESK_CHITCHAT_KEYS = [
    "desk_chitchat_stackchan",
    "desk_chitchat_low_latency",
    "desk_chitchat_watchful",
]

DESK_PHONE_OVERUSE_KEYS = [
    "desk_phone_overuse_1",
    "desk_phone_overuse_2",
    "desk_phone_overuse_3",
    "desk_phone_too_long",
]

DESK_PRIORITIES = [
    ("desk_greeting_1", "顔を検知して着席した時は明るくあいさつする"),
    ("desk_work_start_1", "PC前で手が動き始めたら作業開始としてコメントする"),
    ("desk_typing_fast_1", "タイピングが高速で継続している時は調子の良さを拾う"),
    ("desk_cup_danger_1", "マグカップが机の端やPCの近くにある時は最優先で警告する"),
    ("desk_phone_pickup_1", "スマホを手に取った瞬間は軽く様子を見る"),
    ("desk_phone_overuse_1", "スマホ状態が長く続く時は少し強めに作業復帰を促す"),
    ("desk_yawn_1", "あくびを検知したら軽くツッコむ"),
    ("desk_focus_achieved_1", "長時間集中を達成したら称賛して締める"),
    ("desk_mug_near_edge", "マグカップが机の端やPCの近くにある時は警告する"),
    ("desk_hand_between_cup_keyboard", "手の通り道にカップがある時は事故リスクとして扱う"),
    ("desk_posture_long_still", "長時間同じ姿勢ならストレッチを促す"),
    ("desk_typing_stopped", "手が止まった・詰まっている様子なら軽く声をかける"),
    ("desk_hydration", "飲み物を飲んだら肯定的に反応する"),
    ("desk_clutter_warning", "机が散らかってきたら片付けを促す"),
    ("desk_lighting_dark", "暗い時は照明を促す"),
]

DESK_PHASE_FALLBACK_KEYS = {
    "idle": ["desk_demo_intro", "desk_chitchat_stackchan", "desk_silence_focus"],
    "greeting": ["desk_greeting_1", "desk_greeting_2", "desk_greeting_3"],
    "work_start": ["desk_work_start_1", "desk_work_start_2", "desk_work_start_3", "desk_work_start", "desk_beat_working"],
    "focused_work": [
        "desk_beat_focus",
        "desk_beat_typing",
        "desk_focus_good",
        "desk_typing_fast",
        "desk_focus_one_hour",
        "desk_posture_long_still",
    ],
    "typing_fast": ["desk_typing_fast_1", "desk_typing_fast_2", "desk_typing_fast_3", "desk_typing_fast"],
    "stuck": ["desk_typing_stopped", "desk_repeated_motion", "desk_silence_focus"],
    "break": ["desk_yawn", "desk_hydration", "desk_chitchat_watchful"],
    "hydration": ["desk_hydration"],
    "phone": ["desk_phone_pickup", "desk_beat_phone_watch", "desk_phone_too_long"],
    "phone_pickup": ["desk_phone_pickup_1", "desk_phone_pickup_2", "desk_phone_pickup_3", "desk_phone_pickup"],
    "phone_overuse": ["desk_phone_overuse_1", "desk_phone_overuse_2", "desk_phone_overuse_3", "desk_phone_too_long"],
    "desk_risk": [
        "desk_mug_near_edge",
        "desk_mug_near_pc",
        "desk_hand_between_cup_keyboard",
        "desk_beat_cup_watch",
    ],
    "cup_danger": ["desk_cup_danger_1", "desk_cup_danger_2", "desk_cup_danger_3", "desk_mug_near_edge"],
    "cleanup": ["desk_clutter_warning"],
    "lighting": ["desk_lighting_dark"],
    "yawn": ["desk_yawn_1", "desk_yawn_2", "desk_yawn_3", "desk_yawn"],
    "focus_achieved": ["desk_focus_achieved_1", "desk_focus_achieved_2", "desk_focus_achieved_3", "desk_focus_one_hour"],
    "unknown": ["desk_unknown_scene", "desk_camera_blurry", "desk_lighting_dark"],
}


class BridgeState:
    def __init__(self, audio_dir: Path, static_dir: Path, capture_dir: Path) -> None:
        self.audio_dir = audio_dir
        self.static_dir = static_dir
        self.capture_dir = capture_dir
        self.voice_lines = _load_voice_lines(
            Path("data/desk_voice_lines.json"),
            audio_dir / "manifest.json",
        )
        self.demo_states = _load_demo_states(Path("data/desk_demo_states.json"))
        self.demo_variant_index: dict[str, int] = {}
        self.last_action: dict[str, Any] | None = None
        self.history: list[dict[str, Any]] = []


def _load_voice_lines(*paths: Path) -> dict[str, str]:
    lines: dict[str, str] = {}
    for path in paths:
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        items = payload.get("files", []) if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict) and item.get("key") and item.get("text") is not None:
                lines[str(item["key"])] = str(item["text"])
    return lines


def _load_demo_states(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict) and item.get("state")]


def serve(host: str, port: int, audio_dir: Path, static_dir: Path, capture_dir: Path) -> None:
    load_dotenv(".env")
    state = BridgeState(audio_dir, static_dir, capture_dir)

    class Handler(BaseHTTPRequestHandler):
        server_version = "DeskChanBridge/0.1"

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                self._json({"ok": True})
                return
            if parsed.path == "/last-action":
                self._json({"ok": True, "action": state.last_action})
                return
            if parsed.path == "/api/history":
                self._json({"ok": True, "history": state.history})
                return
            if parsed.path == "/api/demo-states":
                self._json({"ok": True, "states": state.demo_states})
                return
            if parsed.path == "/api/camera.jpg":
                self._proxy_camera(parse_qs(parsed.query))
                return
            if parsed.path.startswith("/audio/"):
                self._serve_file(
                    state.audio_dir / Path(parsed.path.removeprefix("/audio/")).name,
                    not_found_message="audio not found",
                )
                return
            if parsed.path == "/":
                self._serve_file(state.static_dir / "index.html")
                return
            if parsed.path in {"/app.js", "/styles.css"}:
                self._serve_file(state.static_dir / Path(parsed.path).name)
                return
            self._json({"ok": False, "message": "not found"}, status=HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/api/analyze":
                self._handle_analyze()
                return
            if parsed.path == "/api/demo-action":
                self._handle_demo_action()
                return
            if parsed.path == "/api/reset-history":
                state.history.clear()
                self._json({"ok": True, "history": state.history})
                return
            if parsed.path != "/action":
                self._json({"ok": False, "message": "not found"}, status=HTTPStatus.NOT_FOUND)
                return
            try:
                payload = self._read_json()
            except json.JSONDecodeError as error:
                self._json(
                    {"ok": False, "message": f"invalid json: {error}"},
                    status=HTTPStatus.BAD_REQUEST,
                )
                return
            state.last_action = payload
            print(json.dumps({"received_action": payload}, ensure_ascii=False), flush=True)
            self._json({"ok": True, "received": payload})

        def log_message(self, fmt: str, *args: Any) -> None:
            print(f"{self.address_string()} - {fmt % args}", flush=True)

        def _serve_file(self, path: Path, not_found_message: str = "file not found") -> None:
            if not path.exists() or not path.is_file():
                self._json({"ok": False, "message": not_found_message}, status=HTTPStatus.NOT_FOUND)
                return
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            data = path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _proxy_camera(self, query: dict[str, list[str]]) -> None:
            stackchan_url = query.get("stackchan_url", ["http://192.168.11.15"])[0].rstrip("/")
            cache_bust = query.get("t", [""])[0]
            url = f"{stackchan_url}/capture.jpg"
            if cache_bust:
                url = f"{url}?t={cache_bust}"
            try:
                with urllib.request.urlopen(url, timeout=8.0) as response:
                    data = response.read()
                    content_type = response.headers.get("Content-Type", "image/jpeg")
            except Exception as error:
                self._json(
                    {"ok": False, "message": f"camera fetch failed: {error}"},
                    status=HTTPStatus.BAD_GATEWAY,
                )
                return
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _handle_analyze(self) -> None:
            try:
                request = self._read_json()
            except json.JSONDecodeError as error:
                self._json(
                    {"ok": False, "message": f"invalid json: {error}"},
                    status=HTTPStatus.BAD_REQUEST,
                )
                return

            stackchan_url = str(request.get("stackchan_url") or "http://192.168.11.15").rstrip("/")
            provider_name = str(request.get("provider") or "gemini")
            prompt = str(
                request.get("prompt")
                or (
                    "StackChanのカメラ画像を見て、卓上作業の一言を返して。"
                    "手元、キーボード、PC、マグカップ、スマホ、姿勢、照明、散らかり具合を見て、"
                    "短く面白く、必要なら注意や休憩提案を言って。"
                )
            )
            send_to_stackchan = bool(request.get("send_to_stackchan", True))
            use_history = bool(request.get("use_history", True))
            auto_mode = bool(request.get("auto_mode", False))
            stackchan_action_url = str(request.get("stackchan_action_url") or f"{stackchan_url}/action")
            audio_base_url = str(
                request.get("audio_base_url")
                or os.getenv("DESKCHAN_AUDIO_BASE_URL", "")
            ).rstrip("/")

            try:
                image_path = capture_snapshot(stackchan_url, state.capture_dir)
                contextual_prompt = self._with_desk_context(prompt)
                contextual_prompt = self._with_auto_mode(contextual_prompt) if auto_mode else contextual_prompt
                contextual_prompt = self._with_history(contextual_prompt) if use_history else contextual_prompt
                result = get_provider(provider_name).complete(contextual_prompt, image_path)
                data = self._avoid_repeated_utterance(result.data, auto_mode=auto_mode)
                packet = to_action_packet(data)
                self._add_audio_timing(packet)
                self._add_motion_timing(packet)
                if audio_base_url and packet.get("audio", {}).get("path"):
                    packet["audio"]["url"] = f"{audio_base_url}{packet['audio']['path']}"
                send_result = self._post_stackchan_if_requested(
                    send_to_stackchan,
                    stackchan_action_url,
                    packet,
                )
            except Exception as error:
                self._json(
                    {"ok": False, "message": str(error)},
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                )
                return

            state.last_action = packet
            history_item = self._history_item(data, str(image_path))
            state.history.append(history_item)
            state.history = state.history[-16:]
            self._json(
                {
                    "ok": True,
                    "provider": result.provider,
                    "model": result.model,
                    "latency_ms": result.latency_ms,
                    "image_path": str(image_path),
                    "history": state.history,
                    "data": data,
                    "stackchan_packet": packet,
                    "stackchan_post": send_result,
                }
            )

        def _handle_demo_action(self) -> None:
            try:
                request = self._read_json()
            except json.JSONDecodeError as error:
                self._json(
                    {"ok": False, "message": f"invalid json: {error}"},
                    status=HTTPStatus.BAD_REQUEST,
                )
                return

            state_name = str(request.get("state") or "")
            demo_state = self._find_demo_state(state_name)
            if demo_state is None:
                self._json(
                    {"ok": False, "message": f"unknown demo state: {state_name}"},
                    status=HTTPStatus.BAD_REQUEST,
                )
                return

            stackchan_url = str(request.get("stackchan_url") or "http://192.168.11.15").rstrip("/")
            stackchan_action_url = str(request.get("stackchan_action_url") or f"{stackchan_url}/action")
            audio_base_url = str(
                request.get("audio_base_url")
                or os.getenv("DESKCHAN_AUDIO_BASE_URL", "")
            ).rstrip("/")
            send_to_stackchan = bool(request.get("send_to_stackchan", True))
            variant_index = request.get("variant_index")

            try:
                data = self._demo_response(demo_state, variant_index)
                packet = to_action_packet(data)
                self._add_audio_timing(packet)
                self._add_motion_timing(packet)
                if audio_base_url and packet.get("audio", {}).get("path"):
                    packet["audio"]["url"] = f"{audio_base_url}{packet['audio']['path']}"
                send_result = self._post_stackchan_if_requested(
                    send_to_stackchan,
                    stackchan_action_url,
                    packet,
                )
            except Exception as error:
                self._json(
                    {"ok": False, "message": str(error)},
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                )
                return

            state.last_action = packet
            history_item = self._history_item(data, "scripted-demo")
            state.history.append(history_item)
            state.history = state.history[-16:]
            self._json(
                {
                    "ok": True,
                    "provider": "scripted",
                    "model": "desk-demo-script",
                    "latency_ms": 0,
                    "demo_state": demo_state,
                    "history": state.history,
                    "data": data,
                    "stackchan_packet": packet,
                    "stackchan_post": send_result,
                }
            )

        def _post_stackchan_if_requested(
            self,
            send_to_stackchan: bool,
            stackchan_action_url: str,
            packet: dict[str, Any],
        ) -> dict[str, Any] | None:
            if not send_to_stackchan:
                return None
            try:
                return post_action(stackchan_action_url, packet, timeout_seconds=8.0)
            except Exception as error:
                return {"ok": False, "message": str(error), "url": stackchan_action_url}

        def _find_demo_state(self, state_name: str) -> dict[str, Any] | None:
            for item in state.demo_states:
                if item.get("state") == state_name:
                    return item
            return None

        def _demo_response(
            self,
            demo_state: dict[str, Any],
            variant_index: Any,
        ) -> dict[str, Any]:
            variants = demo_state.get("variants", [])
            if not isinstance(variants, list) or not variants:
                raise ValueError(f"demo state has no variants: {demo_state.get('state')}")
            state_name = str(demo_state.get("state"))
            if variant_index is None:
                index = state.demo_variant_index.get(state_name, 0) % len(variants)
                state.demo_variant_index[state_name] = index + 1
            else:
                index = max(0, min(int(variant_index), len(variants) - 1))
            variant = variants[index]
            if not isinstance(variant, dict):
                raise ValueError(f"invalid demo variant: {state_name}")
            audio_key = str(variant["key"])
            text = str(variant["text"])
            return {
                "reply": text,
                "safety_level": str(demo_state.get("safety_level", "ok")),
                "desk_phase": state_name,
                "stackchan": {
                    "expression": str(demo_state.get("expression", "happy")),
                    "motion": str(demo_state.get("motion", "nod")),
                    "audio_key": audio_key,
                    "intensity": int(demo_state.get("intensity", 2)),
                },
                "actions": [str(demo_state.get("trigger", ""))],
                "timers": [],
                "visual_checklist": ["顔", "手元", "キーボード", "マグカップ", "スマホ"],
                "agent_notes": [
                    {"agent": "vision", "vote": str(demo_state.get("trigger", state_name))},
                    {"agent": "strategy", "vote": str(demo_state.get("tone", ""))},
                    {"agent": "banter", "vote": audio_key},
                ],
                "demo_caption": f"{demo_state.get('label', state_name)}: {demo_state.get('trigger', '')}",
            }

        def _with_desk_context(self, prompt: str) -> str:
            completed = [
                str(item.get("audio_key", ""))
                for item in state.history
                if item.get("audio_key")
            ]
            completed_text = ", ".join(completed[-10:]) if completed else "なし"
            lines = [prompt, "", "卓上判断の優先事項:"]
            for index, (key, label) in enumerate(DESK_PRIORITIES, start=1):
                lines.append(f"{index}. {label}: {key}")
            lines.extend(
                [
                    "",
                    "卓上判断ルール:",
                    "- 現在の画像を最優先する。履歴は過去の観察であり、現フレームと矛盾する時は現フレームを信じる。",
                    "- 画像が暗い、斜め、ブレ、机の一部だけの場合は desk_phase を unknown にして撮影調整を促す。",
                    "- 手、キーボード、PC、マグカップ、スマホ、姿勢、席の有無、照明、散らかり具合を読む。",
                    "- カップが机の端、PCの近く、手の通り道にある場合は safety_level を warn にして短く警告する。",
                    "- スマホを持った直後は軽く反応し、履歴上長く続く場合だけ phone_overuse / desk_phone_overuse_* を選ぶ。",
                    "- 同じ認識結果が続く場合は同じ発話を繰り返さない。スマホ継続以外は意味のある沈黙にする。",
                    "- 長時間の集中や同じ姿勢は、褒めるか軽く休憩を促す。過度に個人を監視する言い方にしない。",
                    "- 危険状態が続く時だけ再警告する。毎秒同じ警告を繰り返さない。",
                    "- 1回の返答は自然な短文にする。説明口調で長くしない。",
                    f"- 直近で指示した audio_key: {completed_text}",
                ]
            )
            return "\n".join(lines)

        def _with_history(self, prompt: str) -> str:
            if not state.history:
                return prompt
            lines = [
                prompt,
                "",
                "前後関係:",
                "- 以下は直前までに観察した履歴です。",
                "- 現在の画像を優先しつつ、流れは履歴と矛盾しないように判断してください。",
                "- 直近で使った audio_key と同じ audio_key は選ばないでください。",
                "- 同じ状況が続く場合は、同じ助言を繰り返さず、原則として意味のある沈黙を選んでください。",
                "- phone / phone_pickup が続くなら desk_phone_pickup ではなく phone_overuse / desk_phone_overuse_* に寄せる。",
                "- cup_danger, typing_fast, greeting, work_start などが続くなら警告や同じ反応を繰り返さず沈黙する。",
            ]
            for index, item in enumerate(state.history[-8:], start=1):
                lines.append(
                    f"{index}. phase={item['desk_phase']}, safety={item['safety_level']}, "
                    f"audio={item['audio_key']}, reply={item['reply']}"
                )
            return "\n".join(lines)

        def _with_auto_mode(self, prompt: str) -> str:
            return "\n".join(
                [
                    prompt,
                    "",
                    "自動モード:",
                    "- 約1から2秒ごとに呼ばれる前提で、短い desk_beat_* も使ってテンポを保つ。",
                    "- ただし、意味のある沈黙は作る。変化がない時や画面更新待ちでは desk_silence_focus を選んでよい。",
                    "- 前回と状況が変わらない場合は、同じ長い助言を繰り返さず、原則として desk_silence_focus を選ぶ。",
                    "- ユーザーは作業中でPCを触れない。画像を見て必要なタイミングで自律的にコメントする。",
                    "- 同じ局面でも目線を変える。手元、姿勢、カップ、スマホ、照明、散らかり、カメラ状態から別の観察を話す。",
                    "- 1回の返答は短く、StackChanがすぐ喋れる長さにする。",
                ]
            )

        def _avoid_repeated_utterance(self, data: dict[str, Any], *, auto_mode: bool) -> dict[str, Any]:
            stackchan = data.get("stackchan", {})
            current_key = str(stackchan.get("audio_key", ""))
            current_reply = str(data.get("reply", ""))
            recent = state.history[-6:]
            recent_keys = [str(item.get("audio_key", "")) for item in recent]
            recent_replies = [str(item.get("reply", "")) for item in recent]
            if not current_key:
                return data
            continuation = self._continuation_override(data, recent_keys, auto_mode=auto_mode)
            if continuation is not None:
                return continuation
            if data.get("safety_level") == "stop" and current_key not in recent_keys[-2:]:
                return data
            repeated_phase = (
                auto_mode
                and recent
                and str(recent[-1].get("desk_phase", "")) == str(data.get("desk_phase", ""))
            )
            if not repeated_phase and current_key not in recent_keys and current_reply not in recent_replies:
                return data

            replacement_key = self._pick_replacement_key(data, recent_keys, auto_mode=auto_mode)
            if not replacement_key or replacement_key == current_key:
                return data

            updated = json.loads(json.dumps(data, ensure_ascii=False))
            updated["reply"] = state.voice_lines.get(replacement_key, current_reply)
            updated["stackchan"]["audio_key"] = replacement_key
            if auto_mode and "chitchat" in replacement_key:
                updated["stackchan"]["expression"] = "happy"
                updated["stackchan"]["motion"] = self._motion_for_history()
                updated["stackchan"]["intensity"] = max(1, int(updated["stackchan"].get("intensity", 1)))
            elif replacement_key in DESK_WAIT_KEYS:
                updated["stackchan"]["expression"] = "serious"
                updated["stackchan"]["motion"] = self._motion_for_history()
                updated["stackchan"]["intensity"] = max(1, int(updated["stackchan"].get("intensity", 1)))
            updated["demo_caption"] = "同じ局面では発話をローテーションして、作業中も邪魔しすぎない。"
            updated["agent_notes"] = [
                {"agent": "vision", "vote": str(data.get("desk_phase", "unknown"))},
                {"agent": "strategy", "vote": str(data.get("safety_level", "ok"))},
                {"agent": "banter", "vote": f"dedup:{current_key}->{replacement_key}"},
            ]
            return updated

        def _continuation_override(
            self,
            data: dict[str, Any],
            recent_keys: list[str],
            *,
            auto_mode: bool,
        ) -> dict[str, Any] | None:
            if not auto_mode:
                return None
            group = self._phase_group(str(data.get("desk_phase", "unknown")))
            relevant_history = state.history
            if not relevant_history:
                return None

            streak: list[dict[str, Any]] = []
            for item in reversed(relevant_history):
                if self._phase_group(str(item.get("desk_phase", ""))) != group:
                    break
                streak.append(item)
            if not streak:
                return None

            current_key = str(data.get("stackchan", {}).get("audio_key", ""))
            if current_key.endswith("_silence_focus"):
                return self._make_silent_continuation(data, group, len(streak))

            if group == "phone":
                same_group_keys = [str(item.get("audio_key", "")) for item in reversed(streak)]
                overuse_recent = any(key in DESK_PHONE_OVERUSE_KEYS for key in same_group_keys[-4:])
                if len(streak) >= 2 and not overuse_recent:
                    return self._make_phone_overuse(data, recent_keys, len(streak))
            return self._make_silent_continuation(data, group, len(streak))

        def _phase_group(self, phase: str) -> str:
            groups = {
                "phone": "phone",
                "phone_pickup": "phone",
                "phone_overuse": "phone",
                "cup_danger": "cup_risk",
                "desk_risk": "cup_risk",
            }
            return groups.get(phase, phase)

        def _make_silent_continuation(
            self,
            data: dict[str, Any],
            group: str,
            repeated_count: int,
        ) -> dict[str, Any] | None:
            updated = json.loads(json.dumps(data, ensure_ascii=False))
            updated["reply"] = "（同じ状態が続いているので見守り中）"
            stackchan = updated.setdefault("stackchan", {})
            stackchan["audio_key"] = "desk_silence_focus"
            stackchan["expression"] = "neutral"
            stackchan["motion"] = "none"
            stackchan["intensity"] = 0
            updated["demo_caption"] = "同じ状態が継続しているため、連続発話せずに見守る。"
            updated["agent_notes"] = [
                {"agent": "vision", "vote": str(data.get("desk_phase", "unknown"))},
                {"agent": "strategy", "vote": "same_state_silence"},
                {"agent": "banter", "vote": f"silent:{group}:repeat={repeated_count + 1}"},
            ]
            return updated

        def _make_phone_overuse(
            self,
            data: dict[str, Any],
            recent_keys: list[str],
            repeated_count: int,
        ) -> dict[str, Any] | None:
            available = [key for key in DESK_PHONE_OVERUSE_KEYS if key in state.voice_lines]
            if not available:
                return self._make_silent_continuation(data, "phone", repeated_count)
            replacement_key = self._first_available_not_recent(available, recent_keys)
            updated = json.loads(json.dumps(data, ensure_ascii=False))
            updated["reply"] = state.voice_lines.get(replacement_key, str(data.get("reply", "")))
            updated["safety_level"] = "warn"
            updated["desk_phase"] = "phone_overuse"
            stackchan = updated.setdefault("stackchan", {})
            stackchan["audio_key"] = replacement_key
            stackchan["expression"] = "serious"
            stackchan["motion"] = "tilt_left"
            stackchan["intensity"] = max(1, int(stackchan.get("intensity", 1)))
            updated["demo_caption"] = "スマホ状態が時系列で続いたため、過使用として一度だけ声をかける。"
            updated["agent_notes"] = [
                {"agent": "vision", "vote": str(data.get("desk_phase", "unknown"))},
                {"agent": "strategy", "vote": f"phone_continued:{repeated_count + 1}"},
                {"agent": "banter", "vote": f"phone_overuse:{replacement_key}"},
            ]
            return updated

        def _pick_replacement_key(
            self,
            data: dict[str, Any],
            recent_keys: list[str],
            *,
            auto_mode: bool,
        ) -> str | None:
            phase = str(data.get("desk_phase", "unknown"))
            candidates: list[str] = []
            if auto_mode:
                last_phase = str(state.history[-1].get("desk_phase", "")) if state.history else ""
                if phase == last_phase:
                    if phase in {"phone", "phone_pickup", "phone_overuse"}:
                        candidates.extend(DESK_PHONE_OVERUSE_KEYS)
                    else:
                        candidates.extend(DESK_CHITCHAT_KEYS)
                    available = [key for key in candidates if key in state.voice_lines]
                    if available:
                        return self._first_available_not_recent(available, recent_keys)
                if phase == last_phase and phase in {"focused_work", "phone", "desk_risk", "stuck"}:
                    candidates.extend(DESK_WAIT_KEYS)
                    candidates.extend(DESK_PHASE_FALLBACK_KEYS.get(phase, []))
                    candidates.extend(DESK_CHITCHAT_KEYS)
            candidates.extend(DESK_PHASE_FALLBACK_KEYS.get(phase, []))
            candidates.extend(DESK_CHITCHAT_KEYS)

            available = [key for key in candidates if key in state.voice_lines]
            if not available:
                return None
            return self._first_available_not_recent(available, recent_keys)

        def _first_available_not_recent(self, available: list[str], recent_keys: list[str]) -> str:
            blocked = set(recent_keys[-4:])
            for offset in range(len(available)):
                index = (len(state.history) + offset) % len(available)
                key = available[index]
                if key not in blocked:
                    return key
            for key in available:
                if key not in recent_keys[-1:]:
                    return key
            return available[len(state.history) % len(available)]

        def _motion_for_history(self) -> str:
            return ["tilt_left", "tilt_right", "nod", "bounce"][len(state.history) % 4]

        def _history_item(self, data: dict[str, Any], image_path: str) -> dict[str, Any]:
            stackchan = data.get("stackchan", {})
            return {
                "time": time.strftime("%H:%M:%S"),
                "timestamp_ms": int(time.time() * 1000),
                "reply": data.get("reply", ""),
                "desk_phase": data.get("desk_phase", "unknown"),
                "phase_group": self._phase_group(str(data.get("desk_phase", "unknown"))),
                "safety_level": data.get("safety_level", "ok"),
                "audio_key": stackchan.get("audio_key", ""),
                "silent": str(stackchan.get("audio_key", "")).endswith("_silence_focus"),
                "motion": stackchan.get("motion", ""),
                "image_path": image_path,
            }

        def _add_audio_timing(self, packet: dict[str, Any]) -> None:
            audio = packet.get("audio")
            if not isinstance(audio, dict):
                return
            audio_key = str(audio.get("key", ""))
            if not audio_key:
                return
            duration_ms = self._wav_duration_ms(audio_key)
            if duration_ms <= 0:
                return
            audio["duration_ms"] = duration_ms
            audio["estimated_stackchan_playback_ms"] = int(duration_ms / 0.8)

        def _add_motion_timing(self, packet: dict[str, Any]) -> None:
            motion = str(packet.get("motion", "none"))
            try:
                intensity = int(packet.get("intensity", 1))
            except (TypeError, ValueError):
                intensity = 1
            packet["estimated_stackchan_motion_ms"] = self._motion_duration_ms(motion, intensity)

        def _motion_duration_ms(self, motion: str, intensity: int) -> int:
            level = min(3, max(0, intensity))
            duration_ms = 420 + level * 90
            motion = motion.strip()
            if motion in {"", "none", "stop"}:
                return 0
            if motion in {"nod", "tilt_left", "tilt_right"}:
                return duration_ms + 450 + 550
            if motion == "shake":
                return duration_ms + 500 + 550
            if motion == "bounce":
                return duration_ms + 420 + 550
            if motion == "rotate":
                return 900 + level * 220 + 600
            return duration_ms

        def _wav_duration_ms(self, audio_key: str) -> int:
            path = state.audio_dir / f"{audio_key}.wav"
            if not path.exists():
                return 0
            try:
                with wave.open(str(path), "rb") as wav:
                    frames = wav.getnframes()
                    rate = wav.getframerate()
            except Exception:
                return 0
            if rate <= 0:
                return 0
            return int(frames / rate * 1000)

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            return json.loads(raw.decode("utf-8"))

        def _json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"DeskChan bridge listening on http://{host}:{port}", flush=True)
    print(f"Serving audio from {audio_dir}", flush=True)
    print(f"Serving vision UI from {static_dir}", flush=True)
    print(f"Saving captures to {capture_dir}", flush=True)
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m deskchan.bridge")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--audio-dir", type=Path, default=Path("public/audio"))
    parser.add_argument("--static-dir", type=Path, default=Path("public/vision"))
    parser.add_argument("--capture-dir", type=Path, default=Path("artifacts/captures"))
    args = parser.parse_args()
    serve(args.host, args.port, args.audio_dir, args.static_dir, args.capture_dir)


if __name__ == "__main__":
    main()
