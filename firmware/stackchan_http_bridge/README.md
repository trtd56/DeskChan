# StackChan HTTP Bridge Firmware

This firmware replaces the current StackChan firmware with a minimal HTTP bridge for the hackathon demo.

## What It Does

- Connects to Wi-Fi with static IP `192.168.11.15`.
- Exposes `GET /health`.
- Exposes `POST /action`.
- Exposes `POST /face`, compatible with the StackChan manzai firmware style in `../stack_reachy`.
- Shows the received expression on the CoreS3 display and keeps the latest Tetris action state.
- Plays the provided WAV audio URL. If the WAV cannot be fetched, it stays silent by default.
- Probes the audio URL when `audio.url` is provided, or when `audio.path` is provided with `AUDIO_BASE_URL`.

## Wi-Fi Setup

Copy the example config:

```bash
cp include/wifi_config.example.h include/wifi_config.h
```

Edit `include/wifi_config.h`:

```cpp
#define WIFI_SSID "YOUR_2_4GHZ_WIFI_SSID"
#define WIFI_PASSWORD "YOUR_WIFI_PASSWORD"
#define STACKCHAN_STATIC_IP "192.168.11.15"
#define STACKCHAN_GATEWAY_IP "192.168.11.1"
#define STACKCHAN_SUBNET_IP "255.255.255.0"
#define STACKCHAN_DNS_IP "192.168.11.1"
#define AUDIO_BASE_URL "http://192.168.0.10:8787"
#define ENABLE_FEEDBACK_TONE 0
```

Use a 2.4GHz SSID. ESP32-S3 does not connect to 6GHz Wi-Fi.

`AUDIO_BASE_URL` is only a fallback. The Python sender can also include an absolute
`audio.url` by setting `TETRIS_CHAN_AUDIO_BASE_URL`. Keep the bridge bound to
`0.0.0.0`, not `127.0.0.1`, so StackChan can fetch the WAV from your Mac LAN IP.

## Build

```bash
pio run
```

## Flash

This overwrites the current StackChan firmware.

```bash
pio run -t upload --upload-port /dev/cu.usbmodem1101
```

## Monitor

```bash
pio device monitor --port /dev/cu.usbmodem1101 --baud 115200
```

## Test

From the project root:

```bash
export TETRIS_CHAN_AUDIO_BASE_URL=http://192.168.0.10:8787
PYTHONPATH=src python3 -m kitchen_chan.cli device send "右端井戸が空いていて、Iミノ待ち。短く実況して" \
  --provider mock \
  --transport http \
  --url http://192.168.11.15/action
```

Health check:

```bash
curl http://192.168.11.15/health
```

Face-only test:

```bash
curl -X POST http://192.168.11.15/face \
  -H 'Content-Type: application/json' \
  -d '{"face":"retort","source":"画面：ツッコミ顔"}'
```

Known face names borrowed from `../stack_reachy/firmware/stackchan_manzai`:

- `neutral`
- `smile`
- `gentle_smile`
- `smug`
- `grin`
- `sparkle`
- `retort`
- `suspicious`
- `question`
- `stare`
- `awkward`
- `look_up`
- `look_down`
- `blank`
- `tearful`
- `scared`
- `heart`
- `mouth_smile`
- `mouth_talk`
