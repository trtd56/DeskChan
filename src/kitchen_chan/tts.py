from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


def main() -> None:
    load_dotenv(".env")
    parser = argparse.ArgumentParser(prog="python -m kitchen_chan.tts")
    parser.add_argument("--input", type=Path, default=Path("data/tetris_voice_lines.json"))
    parser.add_argument("--out", type=Path, default=Path("public/audio"))
    parser.add_argument("--model", default=os.getenv("GEMINI_TTS_MODEL", "gemini-3.1-flash-tts-preview"))
    parser.add_argument("--voice", default="Puck")
    parser.add_argument("--speed", type=float, default=1.2, help="Post-process playback speed multiplier.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    lines = json.loads(args.input.read_text(encoding="utf-8"))
    args.out.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "model": args.model,
        "voice": args.voice,
        "speed": args.speed,
        "files": [],
    }

    for line in lines:
        key = line["key"]
        silent = bool(line.get("silent")) or key.endswith("_silence_focus")
        out_path = args.out / f"{key}.wav"
        manifest_item = {
            "key": key,
            "text": line["text"],
            "prompt": line["prompt"],
        }
        if silent:
            manifest_item["silent"] = True
        else:
            manifest_item["path"] = str(out_path)
        manifest["files"].append(manifest_item)
        if args.dry_run:
            print(f"{key}: {line['text']}")
            continue
        if silent:
            print(f"skipped silent {key}")
            continue
        generate_wav(line["prompt"], out_path, model=args.model, voice=args.voice, speed=args.speed)
        print(f"wrote {out_path}")

    manifest_path = args.out / "manifest.json"
    if args.dry_run:
        return
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {manifest_path}")


def generate_wav(prompt: str, out_path: Path, *, model: str, voice: str, speed: float) -> None:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
                )
            ),
        ),
    )
    audio_data = response.candidates[0].content.parts[0].inline_data.data
    pcm = base64.b64decode(audio_data) if isinstance(audio_data, str) else audio_data
    if speed == 1.0:
        write_wave(out_path, pcm)
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        raw_path = Path(tmpdir) / "raw.wav"
        write_wave(raw_path, pcm)
        speed_up_wave(raw_path, out_path, speed)


def write_wave(filename: Path, pcm: bytes, channels: int = 1, rate: int = 24000, sample_width: int = 2) -> None:
    with wave.open(str(filename), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm)


def speed_up_wave(input_path: Path, output_path: Path, speed: float) -> None:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is required for --speed. Install ffmpeg or run with --speed 1.0.")
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(input_path),
            "-filter:a",
            f"atempo={speed}",
            str(output_path),
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
