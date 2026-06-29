from __future__ import annotations

import json
import os
import re
import subprocess
import termios
import time
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_HTTP_ENDPOINTS = [
    "/action",
    "/api/action",
    "/speak",
    "/api/speak",
    "/speech",
    "/api/speech",
    "/message",
    "/api/message",
    "/chat",
    "/api/chat",
]

PROBE_GET_ENDPOINTS = [
    "/",
    "/status",
    "/health",
    "/api",
    "/api/status",
    "/version",
    "/config",
    "/action",
    "/speak",
]


@dataclass(frozen=True)
class StackChanCandidate:
    kind: str
    address: str
    detail: str


def to_action_packet(response: dict[str, Any]) -> dict[str, Any]:
    stackchan = response["stackchan"]
    audio_key = stackchan["audio_key"]
    audio: dict[str, Any] = {"key": audio_key}
    if audio_key.endswith("_silence_focus"):
        audio["silent"] = True
    else:
        audio_path = f"/audio/{audio_key}.wav"
        audio["path"] = audio_path
        audio_base_url = os.getenv("DESKCHAN_AUDIO_BASE_URL", "").rstrip("/")
        if audio_base_url:
            audio["url"] = f"{audio_base_url}{audio_path}"
    return {
        "type": "stackchan.action",
        "text": response["reply"],
        "safety_level": response["safety_level"],
        "desk_phase": response.get("desk_phase", "unknown"),
        "expression": stackchan["expression"],
        "motion": stackchan["motion"],
        "intensity": stackchan["intensity"],
        "audio": audio,
        "timers": response["timers"],
    }


def post_action(url: str, packet: dict[str, Any], timeout_seconds: float = 5.0) -> dict[str, Any]:
    body = json.dumps(packet, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        payload = response.read().decode("utf-8")
    if not payload:
        return {"status": "ok"}
    return json.loads(payload)


def capture_snapshot(base_url: str, out_dir: Path = Path("artifacts/captures"), timeout_seconds: float = 8.0) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"stackchan_capture_{timestamp}.jpg"
    url = f"{base_url.rstrip('/')}/capture.jpg"
    request = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        content_type = response.headers.get("Content-Type", "")
        data = response.read()
    if "image/jpeg" not in content_type:
        raise RuntimeError(f"Expected image/jpeg from {url}, got {content_type}: {data[:200]!r}")
    out_path.write_bytes(data)
    return out_path


def discover_candidates() -> list[StackChanCandidate]:
    candidates: list[StackChanCandidate] = []
    for port in sorted(Path("/dev").glob("cu.*")):
        name = port.name
        if "usbmodem" in name or "usbserial" in name:
            candidates.append(StackChanCandidate("serial", str(port), "USB serial candidate"))

    try:
        profiler = subprocess.run(
            ["system_profiler", "SPUSBDataType"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout
        for serial in re.findall(r"Serial Number: ([0-9A-Fa-f:]{17})", profiler):
            candidates.append(StackChanCandidate("usb-mac", serial.lower(), "Espressif USB serial number"))
    except Exception:
        pass

    try:
        arp = subprocess.run(
            ["arp", "-a"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout
        for ip, mac in re.findall(r"\\((\\d+\\.\\d+\\.\\d+\\.\\d+)\\) at ([0-9a-f:]+)", arp):
            normalized = ":".join(part.zfill(2) for part in mac.split(":")).lower()
            if normalized.startswith(("44:1b:f6", "30:32:35", "24:0a:c4", "7c:df:a1")):
                candidates.append(StackChanCandidate("http", f"http://{ip}", f"Espressif-like MAC {normalized}"))
    except Exception:
        pass

    return _dedupe_candidates(candidates)


def probe_http(base_url: str, timeout_seconds: float = 2.0) -> list[dict[str, Any]]:
    base = base_url.rstrip("/")
    results: list[dict[str, Any]] = []
    for endpoint in PROBE_GET_ENDPOINTS:
        results.append(_request_result("GET", f"{base}{endpoint}", timeout_seconds=timeout_seconds))
    sample = {"text": "テストやで", "expression": "happy", "motion": "nod"}
    for endpoint in DEFAULT_HTTP_ENDPOINTS:
        results.append(
            _request_result(
                "POST",
                f"{base}{endpoint}",
                body=json.dumps(sample, ensure_ascii=False).encode("utf-8"),
                timeout_seconds=timeout_seconds,
            )
        )
    return results


def send_serial_json(port: str, packet: dict[str, Any], baud: int = 115200) -> dict[str, Any]:
    import os

    fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        _configure_serial(fd, baud)
        payload = json.dumps(packet, ensure_ascii=False).encode("utf-8") + b"\n"
        written = os.write(fd, payload)
        time.sleep(0.1)
        return {"status": "sent", "port": port, "baud": baud, "bytes": written}
    finally:
        os.close(fd)


def read_serial(port: str, baud: int = 115200, seconds: float = 5.0) -> str:
    import select

    fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        _configure_serial(fd, baud)
        end = time.time() + seconds
        chunks: list[bytes] = []
        while time.time() < end:
            readable, _, _ = select.select([fd], [], [], 0.2)
            if not readable:
                continue
            try:
                data = os.read(fd, 4096)
            except BlockingIOError:
                continue
            if data:
                chunks.append(data)
        return b"".join(chunks).decode("utf-8", "replace")
    finally:
        os.close(fd)


def _request_result(
    method: str,
    url: str,
    *,
    body: bytes | None = None,
    timeout_seconds: float,
) -> dict[str, Any]:
    headers = {"Content-Type": "application/json"} if body else {}
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = response.read(240).decode("utf-8", "replace")
            status = response.status
            content_type = response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as error:
        payload = error.read(240).decode("utf-8", "replace")
        status = error.code
        content_type = error.headers.get("Content-Type", "")
    except Exception as error:
        return {
            "method": method,
            "url": url,
            "ok": False,
            "error": str(error),
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }
    return {
        "method": method,
        "url": url,
        "ok": 200 <= status < 300,
        "status": status,
        "content_type": content_type,
        "body": payload,
        "latency_ms": int((time.perf_counter() - started) * 1000),
    }


def _configure_serial(fd: int, baud: int) -> None:
    speeds = {
        9600: termios.B9600,
        19200: termios.B19200,
        38400: termios.B38400,
        57600: termios.B57600,
        115200: termios.B115200,
        230400: getattr(termios, "B230400", termios.B115200),
    }
    speed = speeds.get(baud)
    if speed is None:
        raise ValueError(f"Unsupported baud rate: {baud}")
    attrs = termios.tcgetattr(fd)
    attrs[0] = 0
    attrs[1] = 0
    attrs[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
    attrs[3] = 0
    attrs[4] = speed
    attrs[5] = speed
    termios.tcsetattr(fd, termios.TCSANOW, attrs)


def _dedupe_candidates(candidates: list[StackChanCandidate]) -> list[StackChanCandidate]:
    seen: set[tuple[str, str]] = set()
    result: list[StackChanCandidate] = []
    for candidate in candidates:
        key = (candidate.kind, candidate.address)
        if key in seen:
            continue
        seen.add(key)
        result.append(candidate)
    return result
