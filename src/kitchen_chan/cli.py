from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .providers import get_provider
from .stackchan import (
    capture_snapshot,
    discover_candidates,
    post_action,
    probe_http,
    read_serial,
    send_serial_json,
    to_action_packet,
)


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(prog="kitchen-chan")
    subparsers = parser.add_subparsers(dest="command", required=True)

    turn = subparsers.add_parser("turn", help="Run one commentary turn.")
    turn.add_argument("text", help="Current scene situation or user question.")
    turn.add_argument("--scene", choices=["desk", "tetris"], default="desk")
    turn.add_argument("--provider", default="mock", help="mock, gemini, or cerebras.")
    turn.add_argument("--image", type=Path, help="Optional scene image for Gemini.")
    turn.add_argument("--stackchan-camera-url", help="Capture /capture.jpg from StackChan and use it as image input.")
    turn.add_argument("--capture-dir", type=Path, default=Path("artifacts/captures"))
    turn.add_argument("--stackchan-url", help="Optional HTTP endpoint that accepts action JSON.")

    compare = subparsers.add_parser("compare", help="Compare two providers on one prompt.")
    compare.add_argument("text", help="Current scene situation or user question.")
    compare.add_argument("--scene", choices=["desk", "tetris"], default="desk")
    compare.add_argument("--left", default="gemini")
    compare.add_argument("--right", default="cerebras")

    device = subparsers.add_parser("device", help="Discover and test StackChan connectivity.")
    device_subparsers = device.add_subparsers(dest="device_command", required=True)

    device_subparsers.add_parser("discover", help="List likely StackChan USB and HTTP targets.")

    probe = device_subparsers.add_parser("probe", help="Probe a StackChan HTTP base URL.")
    probe.add_argument("--url", default="http://192.168.11.15")

    serial_read = device_subparsers.add_parser("read-serial", help="Read serial output briefly.")
    serial_read.add_argument("--port", default="/dev/cu.usbmodem1101")
    serial_read.add_argument("--baud", type=int, default=115200)
    serial_read.add_argument("--seconds", type=float, default=5.0)

    send = device_subparsers.add_parser("send", help="Generate one action and send it to StackChan.")
    send.add_argument("text", help="Current scene situation or user question.")
    send.add_argument("--scene", choices=["desk", "tetris"], default="desk")
    send.add_argument("--provider", default="mock", help="mock, gemini, or cerebras.")
    send.add_argument("--transport", choices=["print", "http", "serial"], default="print")
    send.add_argument("--url", default="http://192.168.11.15/action")
    send.add_argument("--port", default="/dev/cu.usbmodem1101")
    send.add_argument("--baud", type=int, default=115200)

    bridge = subparsers.add_parser("bridge", help="Run a local StackChan action/audio bridge.")
    bridge.add_argument("--host", default="0.0.0.0")
    bridge.add_argument("--port", type=int, default=8787)
    bridge.add_argument("--audio-dir", type=Path, default=Path("public/audio"))
    bridge.add_argument("--static-dir", type=Path, default=Path("public/vision"))
    bridge.add_argument("--capture-dir", type=Path, default=Path("artifacts/captures"))

    args = parser.parse_args()
    if args.command == "turn":
        image_path = args.image
        if args.stackchan_camera_url:
            image_path = capture_snapshot(args.stackchan_camera_url, args.capture_dir)
        result = get_provider(args.provider).complete(args.text, image_path, scene=args.scene)
        payload = result.__dict__
        if image_path:
            payload["image_path"] = str(image_path)
        payload["stackchan_packet"] = to_action_packet(result.data)
        if args.stackchan_url:
            payload["stackchan_post"] = post_action(args.stackchan_url, payload["stackchan_packet"])
        print(_json(payload))
    elif args.command == "compare":
        left = get_provider(args.left).complete(args.text, scene=args.scene)
        right = get_provider(args.right).complete(args.text, scene=args.scene)
        print(
            _json(
                {
                    "left": left.__dict__,
                    "right": right.__dict__,
                    "latency_delta_ms": left.latency_ms - right.latency_ms,
                }
            )
        )
    elif args.command == "device":
        if args.device_command == "discover":
            print(_json({"candidates": [candidate.__dict__ for candidate in discover_candidates()]}))
        elif args.device_command == "probe":
            print(_json({"url": args.url, "results": probe_http(args.url)}))
        elif args.device_command == "read-serial":
            output = read_serial(args.port, baud=args.baud, seconds=args.seconds)
            print(output if output else "(no serial output)")
        elif args.device_command == "send":
            result = get_provider(args.provider).complete(args.text, scene=args.scene)
            packet = to_action_packet(result.data)
            payload: dict[str, Any] = {
                "provider": result.provider,
                "model": result.model,
                "latency_ms": result.latency_ms,
                "stackchan_packet": packet,
            }
            if args.transport == "http":
                payload["send_result"] = post_action(args.url, packet)
            elif args.transport == "serial":
                payload["send_result"] = send_serial_json(args.port, packet, baud=args.baud)
            print(_json(payload))
    elif args.command == "bridge":
        from .bridge import serve

        serve(args.host, args.port, args.audio_dir, args.static_dir, args.capture_dir)


def _json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
