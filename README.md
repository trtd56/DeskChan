# DeskChan

DeskChan is a StackChan desk companion that watches a workspace camera and reacts with short Japanese lines, expressions, motion, and optional pre-generated audio.

It focuses on desk-work moments such as starting work, fast typing, focus streaks, mug spill risk, phone distraction, dim lighting, clutter, and brief breaks.

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
```

Run a mock turn:

```bash
deskchan turn "マグカップがPCの近くにある。短く注意して"
```

Run the local bridge and browser UI:

```bash
deskchan bridge --host 0.0.0.0 --port 8787
```

Open `http://localhost:8787/`.

## Providers

DeskChan supports:

- `mock`: local rule-based responses for testing without API keys
- `gemini`: Gemini JSON output with optional image input
- `cerebras`: OpenAI-compatible chat completions with optional image input

Set provider credentials in `.env`:

```bash
GEMINI_API_KEY=
CEREBRAS_API_KEY=
```

Example:

```bash
deskchan turn "StackChanのカメラ画像を見て、机の状況を短くコメントして" \
  --provider gemini \
  --stackchan-camera-url http://192.168.11.15
```

## Audio

Pre-generate voice lines from `data/desk_voice_lines.json`:

```bash
python -m deskchan.tts --input data/desk_voice_lines.json --dry-run
python -m deskchan.tts --input data/desk_voice_lines.json --out public/audio --voice Puck --speed 1.5
```

If StackChan should fetch audio from this machine, set the URL served by `deskchan bridge`:

```bash
DESKCHAN_AUDIO_BASE_URL=http://192.168.0.10:8787
```

## StackChan

The HTTP bridge firmware lives in `firmware/stackchan_http_bridge`.

Build:

```bash
cd firmware/stackchan_http_bridge
pio run
```

Upload:

```bash
pio run -t upload --upload-port /dev/cu.usbmodem1101
```

Configure local Wi-Fi settings by copying:

```bash
cp firmware/stackchan_http_bridge/include/wifi_config.example.h \
  firmware/stackchan_http_bridge/include/wifi_config.h
```

`wifi_config.h` is ignored by git.

## CLI

Discover likely StackChan targets:

```bash
deskchan device discover
```

Probe an HTTP endpoint:

```bash
deskchan device probe --url http://192.168.11.15
```

Generate and send one action:

```bash
deskchan device send "スマホを手に取った。短くコメントして" \
  --provider mock \
  --transport http \
  --url http://192.168.11.15/action
```
