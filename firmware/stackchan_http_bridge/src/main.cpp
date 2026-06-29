#include <Arduino.h>
#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <M5CoreS3.h>
#include <M5StackChan.h>
#include <M5Unified.h>
#include <WebServer.h>
#include <WiFi.h>
#include <esp_heap_caps.h>
#include <esp_camera.h>

#if __has_include("wifi_config.h")
#include "wifi_config.h"
#endif

#ifndef WIFI_SSID
#define WIFI_SSID ""
#endif

#ifndef WIFI_PASSWORD
#define WIFI_PASSWORD ""
#endif

#ifndef STACKCHAN_STATIC_IP
#define STACKCHAN_STATIC_IP "192.168.11.15"
#endif

#ifndef STACKCHAN_GATEWAY_IP
#define STACKCHAN_GATEWAY_IP "192.168.11.1"
#endif

#ifndef STACKCHAN_SUBNET_IP
#define STACKCHAN_SUBNET_IP "255.255.255.0"
#endif

#ifndef STACKCHAN_DNS_IP
#define STACKCHAN_DNS_IP "192.168.11.1"
#endif

#ifndef AUDIO_BASE_URL
#define AUDIO_BASE_URL ""
#endif

#ifndef AUDIO_PLAYBACK_RATE_PERCENT
#define AUDIO_PLAYBACK_RATE_PERCENT 100
#endif

#ifndef ENABLE_FEEDBACK_TONE
#define ENABLE_FEEDBACK_TONE 0
#endif

namespace {

WebServer server(80);
String lastActionJson = "{}";
String lastText = "TetrisChan ready";
String lastExpression = "neutral";
String lastAudioKey = "";
String lastGamePhase = "unknown";
uint8_t* audioBuffer = nullptr;
size_t audioBufferLength = 0;
bool isSpeaking = false;
bool mouthOpen = false;
uint32_t nextMouthTick = 0;
uint32_t returnHomeAt = 0;
uint32_t rotateStopAt = 0;
bool cameraReady = false;

constexpr int kBg = TFT_BLACK;
constexpr int kFg = TFT_WHITE;
constexpr int kPitchDown = 0;
constexpr int kPitchUp = 780;

int mapRange(int value, int inMin, int inMax, int outMin, int outMax) {
  value = constrain(value, inMin, inMax);
  return outMin + (value - inMin) * (outMax - outMin) / (inMax - inMin);
}

uint16_t readLe16(const uint8_t* data) {
  return static_cast<uint16_t>(data[0]) | (static_cast<uint16_t>(data[1]) << 8);
}

uint32_t readLe32(const uint8_t* data) {
  return static_cast<uint32_t>(data[0]) |
         (static_cast<uint32_t>(data[1]) << 8) |
         (static_cast<uint32_t>(data[2]) << 16) |
         (static_cast<uint32_t>(data[3]) << 24);
}

void writeLe32(uint8_t* data, uint32_t value) {
  data[0] = value & 0xFF;
  data[1] = (value >> 8) & 0xFF;
  data[2] = (value >> 16) & 0xFF;
  data[3] = (value >> 24) & 0xFF;
}

bool adjustWavPlaybackRate(uint8_t* wav, size_t length) {
  if (AUDIO_PLAYBACK_RATE_PERCENT == 100) return false;
  if (wav == nullptr || length < 36) return false;
  if (memcmp(wav, "RIFF", 4) != 0 || memcmp(wav + 8, "WAVEfmt ", 8) != 0) return false;

  const uint32_t originalRate = readLe32(wav + 24);
  if (originalRate == 0) return false;
  uint32_t adjustedRate = originalRate * AUDIO_PLAYBACK_RATE_PERCENT / 100;
  if (adjustedRate < 8000) adjustedRate = 8000;
  const uint16_t blockAlign = readLe16(wav + 32);

  writeLe32(wav + 24, adjustedRate);
  if (blockAlign > 0) {
    writeLe32(wav + 28, adjustedRate * blockAlign);
  }
  Serial.printf("audio playback rate: %u -> %u (%d%%)\n", originalRate, adjustedRate,
                AUDIO_PLAYBACK_RATE_PERCENT);
  return true;
}

String expressionToReachyFace(const String& expression, const String& safetyLevel, const String& audioKey) {
  if (safetyLevel == "stop") return "scared";
  if (safetyLevel == "warn") return "retort";
  if (expression == "happy") return "smile";
  if (expression == "serious") return "suspicious";
  if (expression == "surprised") return "question";
  if (expression == "angry") return "retort";
  if (expression == "sleepy") return "look_down";
  if (audioKey.indexOf("chitchat") >= 0) return "smug";
  if (audioKey.indexOf("react_nice") >= 0) return "sparkle";
  if (audioKey.indexOf("burn") >= 0 || audioKey.indexOf("smoke") >= 0) return "retort";
  return "neutral";
}

int motionAmount(int intensity, int base, int step) {
  return base + constrain(intensity, 0, 3) * step;
}

int motionDuration(int intensity, int base, int step) {
  return base + constrain(intensity, 0, 3) * step;
}

void scheduleHome(uint32_t delayMs) {
  returnHomeAt = millis() + delayMs;
}

void motionGoHome(int durationMs = 600) {
  rotateStopAt = 0;
  returnHomeAt = 0;
  M5StackChan.Motion.goHome(durationMs);
}

void motionStop() {
  rotateStopAt = 0;
  returnHomeAt = 0;
  M5StackChan.Motion.stop();
}

void applyMotion(const String& motion, int intensity) {
  const int yaw = motionAmount(intensity, 280, 80);
  const int pitch = motionAmount(intensity, 260, 70);
  const int durationMs = motionDuration(intensity, 420, 90);

  if (motion == "none" || motion.isEmpty()) {
    return;
  }
  if (motion == "nod") {
    M5StackChan.Motion.move(0, pitch, durationMs);
    scheduleHome(durationMs + 450);
  } else if (motion == "shake") {
    M5StackChan.Motion.move(yaw, 0, durationMs);
    scheduleHome(durationMs + 500);
  } else if (motion == "tilt_left") {
    M5StackChan.Motion.move(yaw, pitch / 2, durationMs);
    scheduleHome(durationMs + 450);
  } else if (motion == "tilt_right") {
    M5StackChan.Motion.move(-yaw, pitch / 2, durationMs);
    scheduleHome(durationMs + 450);
  } else if (motion == "bounce") {
    M5StackChan.Motion.moveY(kPitchUp, durationMs);
    scheduleHome(durationMs + 420);
  } else if (motion == "look_up") {
    M5StackChan.Motion.moveY(kPitchUp, durationMs);
  } else if (motion == "look_down") {
    M5StackChan.Motion.moveY(kPitchDown, durationMs);
  } else if (motion == "look_left") {
    M5StackChan.Motion.move(yaw, 0, durationMs);
  } else if (motion == "look_right") {
    M5StackChan.Motion.move(-yaw, 0, durationMs);
  } else if (motion == "rotate") {
    const int velocity = motionAmount(intensity, 25, 10);
    M5StackChan.Motion.rotateX(-velocity);
    rotateStopAt = millis() + motionDuration(intensity, 900, 220);
  } else if (motion == "home") {
    motionGoHome(durationMs);
  } else if (motion == "stop") {
    motionStop();
  }
}

void updateMotionTimers() {
  if (rotateStopAt != 0 && static_cast<int32_t>(millis() - rotateStopAt) >= 0) {
    rotateStopAt = 0;
    M5StackChan.Motion.stop();
    M5StackChan.Motion.goHome(600);
  }
  if (returnHomeAt != 0 && static_cast<int32_t>(millis() - returnHomeAt) >= 0) {
    returnHomeAt = 0;
    M5StackChan.Motion.goHome(550);
  }
}

void drawEye(int cx, int cy, int size, int openWeight, int slant, bool left) {
  size = constrain(size, 8, 32);
  openWeight = constrain(openWeight, 0, 100);

  M5.Display.fillCircle(cx, cy, size / 2, kFg);

  const int cover = mapRange(100 - openWeight, 0, 100, 0, size + 4);
  if (cover <= 0) return;

  if (slant == 0) {
    M5.Display.fillRect(cx - size / 2 - 2, cy - size / 2 - 2, size + 4, cover, kBg);
    return;
  }

  int dir = left ? slant : -slant;
  int y0 = cy - size / 2 - 2;
  int x0 = cx - size / 2 - 2;
  int x1 = cx + size / 2 + 2;
  int yLeft = y0 + cover + (dir > 0 ? abs(dir) : 0);
  int yRight = y0 + cover + (dir < 0 ? abs(dir) : 0);
  M5.Display.fillTriangle(x0, y0, x1, y0, x0, yLeft, kBg);
  M5.Display.fillTriangle(x1, y0, x1, yRight, x0, yLeft, kBg);
}

void drawMouth(int weight, int rotationHint = 0) {
  weight = constrain(weight, 0, 100);

  const int cx = 160;
  const int cy = 146;
  const int width = mapRange(weight, 0, 100, 90, 60);
  const int height = mapRange(weight, 0, 100, 6, 50);
  const int radius = mapRange(weight, 0, 100, 0, 16);
  const int x = cx - width / 2;
  const int y = cy - height / 2;

  if (rotationHint == 0) {
    M5.Display.fillRoundRect(x, y, width, height, radius, kFg);
    return;
  }

  const int dy = rotationHint > 0 ? 8 : -8;
  M5.Display.fillTriangle(x, y + height / 2 - 3, x + width, y + height / 2 + dy - 3,
                          x + width, y + height / 2 + dy + 3, kFg);
  M5.Display.fillTriangle(x, y + height / 2 - 3, x, y + height / 2 + 3,
                          x + width, y + height / 2 + dy + 3, kFg);
}

void drawSymbol(const String& text, int color, int textSize, int x, int y) {
  M5.Display.setTextDatum(middle_center);
  M5.Display.setTextColor(color, kBg);
  M5.Display.setTextSize(textSize);
  M5.Display.drawString(text, x, y);
}

void drawReachyStyleFace(const String& face, bool speakingMouthOpen) {
  M5.Display.fillScreen(kBg);

  if (face == "blank") {
    return;
  }

  if (face == "mouth_smile" || face == "mouth_talk") {
    int weight = face == "mouth_talk" || speakingMouthOpen ? 92 : 34;
    M5.Display.fillRoundRect(58, 72, 204, 104, 34, TFT_WHITE);
    M5.Display.fillRoundRect(82, 96, 156, mapRange(weight, 0, 100, 18, 72), 20, TFT_BLACK);
    return;
  }

  int eyeSize = 32;
  int eyeOpen = 100;
  int eyeSlant = 0;
  int mouthWeight = speakingMouthOpen ? 72 : 0;
  int mouthRotation = 0;
  int eyeOffsetX = 0;
  int eyeOffsetY = 0;

  if (face == "neutral") {
    eyeOpen = 100;
    mouthWeight = speakingMouthOpen ? 68 : 0;
  } else if (face == "smile" || face == "gentle_smile" || face == "heart") {
    eyeOpen = 72;
    eyeSlant = 12;
    mouthWeight = speakingMouthOpen ? 74 : 18;
  } else if (face == "smug" || face == "grin" || face == "sparkle") {
    eyeOpen = 62;
    eyeSlant = 8;
    mouthWeight = speakingMouthOpen ? 70 : 10;
    mouthRotation = -1;
  } else if (face == "retort") {
    eyeOpen = 70;
    eyeSlant = -16;
    mouthWeight = speakingMouthOpen ? 78 : 62;
  } else if (face == "suspicious" || face == "question" || face == "stare") {
    eyeOpen = 75;
    mouthWeight = speakingMouthOpen ? 66 : 0;
    eyeOffsetX = face == "stare" ? 4 : 0;
  } else if (face == "awkward") {
    eyeOpen = 60;
    eyeSlant = 8;
    mouthWeight = speakingMouthOpen ? 58 : 0;
    mouthRotation = 1;
  } else if (face == "look_up") {
    eyeOffsetY = -24;
    mouthWeight = speakingMouthOpen ? 68 : 0;
  } else if (face == "look_down") {
    eyeOffsetY = 24;
    mouthWeight = speakingMouthOpen ? 68 : 0;
  } else if (face == "tearful" || face == "scared") {
    eyeOpen = 70;
    eyeSlant = 14;
    mouthWeight = speakingMouthOpen ? 72 : 22;
    eyeOffsetY = 4;
  }

  drawEye(90 + eyeOffsetX, 104 + eyeOffsetY, eyeSize, eyeOpen, eyeSlant, true);
  drawEye(230 + eyeOffsetX, 104 + eyeOffsetY, eyeSize, eyeOpen, eyeSlant, false);
  drawMouth(mouthWeight, mouthRotation);

  if (face == "question") {
    drawSymbol("?", TFT_WHITE, 4, 160, 46);
  } else if (face == "heart") {
    drawSymbol("<3", TFT_RED, 3, 160, 42);
  } else if (face == "sparkle") {
    drawSymbol("*", TFT_YELLOW, 3, 54, 52);
    drawSymbol("*", TFT_YELLOW, 3, 266, 52);
  } else if (face == "tearful") {
    M5.Display.fillCircle(114, 142, 5, TFT_BLUE);
    M5.Display.fillCircle(206, 142, 5, TFT_BLUE);
  } else if (face == "scared") {
    drawSymbol("!", TFT_WHITE, 3, 160, 42);
  }
}

void redrawDisplay() {
  drawReachyStyleFace(lastExpression, isSpeaking && mouthOpen);
}

void replyJson(int status, const JsonDocument& doc) {
  String body;
  serializeJson(doc, body);
  server.send(status, "application/json; charset=utf-8", body);
}

void replyOk(const String& message = "ok") {
  JsonDocument doc;
  doc["ok"] = true;
  doc["message"] = message;
  doc["ip"] = WiFi.localIP().toString();
  replyJson(200, doc);
}

String resolveAudioUrl(JsonObject audio) {
  const char* url = audio["url"] | "";
  if (strlen(url) > 0) return String(url);

  const char* path = audio["path"] | "";
  if (strlen(path) > 0 && strlen(AUDIO_BASE_URL) > 0) {
    return String(AUDIO_BASE_URL) + String(path);
  }
  return "";
}

void playFeedbackTone(const String& safetyLevel) {
  if (safetyLevel == "stop") {
    M5.Speaker.tone(880, 120);
    delay(150);
    M5.Speaker.tone(440, 200);
  } else if (safetyLevel == "warn") {
    M5.Speaker.tone(660, 120);
  } else {
    M5.Speaker.tone(880, 60);
  }
}

void releaseAudioBufferIfIdle() {
  if (audioBuffer != nullptr && !M5.Speaker.isPlaying()) {
    heap_caps_free(audioBuffer);
    audioBuffer = nullptr;
    audioBufferLength = 0;
    isSpeaking = false;
    mouthOpen = false;
    redrawDisplay();
    Serial.println("released audio buffer");
  }
}

bool fetchAndPlayAudio(const String& url) {
  if (url.isEmpty()) return false;

  M5.Speaker.stop();
  if (audioBuffer != nullptr) {
    heap_caps_free(audioBuffer);
    audioBuffer = nullptr;
    audioBufferLength = 0;
  }

  HTTPClient http;
  http.setTimeout(3000);
  if (!http.begin(url)) {
    Serial.printf("audio begin failed: %s\n", url.c_str());
    return false;
  }
  int code = http.GET();
  int length = http.getSize();
  Serial.printf("audio fetch: %s -> %d, %d bytes\n", url.c_str(), code, length);
  if (code != HTTP_CODE_OK || length <= 44 || length > 1400 * 1024) {
    http.end();
    return false;
  }

  audioBuffer = static_cast<uint8_t*>(heap_caps_malloc(length, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
  if (audioBuffer == nullptr) {
    audioBuffer = static_cast<uint8_t*>(heap_caps_malloc(length, MALLOC_CAP_8BIT));
  }
  if (audioBuffer == nullptr) {
    Serial.printf("audio alloc failed: %d bytes\n", length);
    http.end();
    return false;
  }

  WiFiClient* stream = http.getStreamPtr();
  size_t offset = 0;
  uint32_t started = millis();
  while (offset < static_cast<size_t>(length) && millis() - started < 5000) {
    size_t available = stream->available();
    if (available == 0) {
      delay(5);
      continue;
    }
    int readLen = stream->readBytes(
        audioBuffer + offset,
        min(available, static_cast<size_t>(length) - offset));
    if (readLen > 0) {
      offset += readLen;
    }
  }
  http.end();

  if (offset != static_cast<size_t>(length)) {
    Serial.printf("audio read incomplete: %u/%d\n", static_cast<unsigned>(offset), length);
    heap_caps_free(audioBuffer);
    audioBuffer = nullptr;
    audioBufferLength = 0;
    return false;
  }

  audioBufferLength = offset;
  adjustWavPlaybackRate(audioBuffer, audioBufferLength);
  bool startedPlaying = M5.Speaker.playWav(audioBuffer, audioBufferLength, 1, 0, true);
  Serial.printf("audio playWav: %s\n", startedPlaying ? "started" : "failed");
  if (!startedPlaying) {
    heap_caps_free(audioBuffer);
    audioBuffer = nullptr;
    audioBufferLength = 0;
  }
  return startedPlaying;
}

void handleAction() {
  String body = server.arg("plain");
  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, body);
  if (err) {
    JsonDocument res;
    res["ok"] = false;
    res["message"] = String("invalid json: ") + err.c_str();
    replyJson(400, res);
    return;
  }

  lastActionJson = body;
  const char* text = doc["text"] | "";
  const char* safety = doc["safety_level"] | "ok";
  const char* gamePhase = doc["game_phase"] | "unknown";
  const char* expression = doc["expression"] | "neutral";
  const char* motion = doc["motion"] | "none";
  int intensity = doc["intensity"] | 1;
  JsonObject audio = doc["audio"].as<JsonObject>();
  const char* audioKey = audio["key"] | "";
  bool silentAudio = audio["silent"] | false;
  String audioUrl = resolveAudioUrl(audio);

  lastText = text;
  lastGamePhase = gamePhase;
  lastAudioKey = audioKey;
  lastExpression = expressionToReachyFace(String(expression), String(safety), lastAudioKey);
  if (doc["face"].is<const char*>()) {
    lastExpression = String(doc["face"].as<const char*>());
  }
  isSpeaking = true;
  mouthOpen = true;
  nextMouthTick = millis() + 120;

  redrawDisplay();
  applyMotion(String(motion), intensity);
  bool audioPlaying = silentAudio ? false : fetchAndPlayAudio(audioUrl);
  if (!audioPlaying) {
    isSpeaking = false;
#if ENABLE_FEEDBACK_TONE
    if (!silentAudio) {
      playFeedbackTone(String(safety));
    }
#endif
    redrawDisplay();
  }

  JsonDocument res;
  res["ok"] = true;
  res["ip"] = WiFi.localIP().toString();
  res["received"]["text"] = lastText;
  res["received"]["game_phase"] = lastGamePhase;
  res["received"]["safety_level"] = safety;
  res["received"]["expression"] = expression;
  res["received"]["face"] = lastExpression;
  res["received"]["motion"] = motion;
  res["received"]["intensity"] = intensity;
  res["received"]["audio_key"] = lastAudioKey;
  res["received"]["audio_silent"] = silentAudio;
  res["received"]["audio_url"] = audioUrl;
  res["received"]["audio_playing"] = audioPlaying;
  replyJson(200, res);
}

void handleFace() {
  String body = server.arg("plain");
  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, body);
  if (err) {
    JsonDocument res;
    res["ok"] = false;
    res["message"] = String("invalid json: ") + err.c_str();
    replyJson(400, res);
    return;
  }
  const char* face = doc["face"] | "neutral";
  lastExpression = face;
  const char* source = doc["source"] | "";
  if (strlen(source) > 0) {
    lastText = source;
  }
  isSpeaking = doc["speaking"] | false;
  mouthOpen = isSpeaking;
  nextMouthTick = millis() + 120;
  redrawDisplay();

  JsonDocument res;
  res["ok"] = true;
  res["ip"] = WiFi.localIP().toString();
  res["face"] = lastExpression;
  replyJson(200, res);
}

void handleMotion() {
  String body = server.arg("plain");
  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, body);
  if (err) {
    JsonDocument res;
    res["ok"] = false;
    res["message"] = String("invalid json: ") + err.c_str();
    replyJson(400, res);
    return;
  }

  const char* motion = doc["motion"] | "nod";
  int intensity = doc["intensity"] | 2;
  applyMotion(String(motion), intensity);

  JsonDocument res;
  res["ok"] = true;
  res["ip"] = WiFi.localIP().toString();
  res["motion"] = motion;
  res["intensity"] = intensity;
  replyJson(200, res);
}

void handleCapture() {
  if (!cameraReady) {
    JsonDocument res;
    res["ok"] = false;
    res["message"] = "camera not ready";
    replyJson(503, res);
    return;
  }

  if (!CoreS3.Camera.get()) {
    JsonDocument res;
    res["ok"] = false;
    res["message"] = "camera capture failed";
    replyJson(500, res);
    return;
  }

  uint8_t* jpg = nullptr;
  size_t jpgLength = 0;
  bool converted = frame2jpg(CoreS3.Camera.fb, 85, &jpg, &jpgLength);
  CoreS3.Camera.free();

  if (!converted || jpg == nullptr || jpgLength == 0) {
    if (jpg != nullptr) {
      free(jpg);
    }
    JsonDocument res;
    res["ok"] = false;
    res["message"] = "jpeg conversion failed";
    replyJson(500, res);
    return;
  }

  server.sendHeader("Cache-Control", "no-store");
  server.sendHeader("Content-Disposition", "inline; filename=stackchan_capture.jpg");
  server.setContentLength(jpgLength);
  server.send(200, "image/jpeg", "");
  WiFiClient client = server.client();
  client.write(jpg, jpgLength);
  free(jpg);
}

void handleLastAction() {
  JsonDocument res;
  res["ok"] = true;
  res["ip"] = WiFi.localIP().toString();
  res["action_json"] = lastActionJson;
  res["text"] = lastText;
  res["game_phase"] = lastGamePhase;
  res["expression"] = lastExpression;
  res["audio_key"] = lastAudioKey;
  replyJson(200, res);
}

void handleNotFound() {
  JsonDocument res;
  res["ok"] = false;
  res["message"] = "not found";
  res["path"] = server.uri();
  replyJson(404, res);
}

void connectWiFi() {
  IPAddress localIp;
  IPAddress gateway;
  IPAddress subnet;
  IPAddress dns;
  localIp.fromString(STACKCHAN_STATIC_IP);
  gateway.fromString(STACKCHAN_GATEWAY_IP);
  subnet.fromString(STACKCHAN_SUBNET_IP);
  dns.fromString(STACKCHAN_DNS_IP);

  WiFi.mode(WIFI_STA);
  WiFi.config(localIp, gateway, subnet, dns);

  if (strlen(WIFI_SSID) == 0) {
    WiFi.mode(WIFI_AP);
    WiFi.softAP("TetrisChan-Setup");
    Serial.println("WIFI_SSID is empty. Started AP: TetrisChan-Setup");
    lastExpression = "retort";
    lastText = "WiFi config missing. AP: TetrisChan-Setup";
    lastAudioKey = "";
    redrawDisplay();
    return;
  }

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.printf("Connecting to WiFi SSID=%s static_ip=%s\n", WIFI_SSID, STACKCHAN_STATIC_IP);
  lastExpression = "neutral";
  lastText = "WiFi connecting...";
  lastAudioKey = "";
  redrawDisplay();

  uint32_t started = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - started < 20000) {
    delay(300);
    Serial.print(".");
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("WiFi connected: %s\n", WiFi.localIP().toString().c_str());
    lastExpression = "neutral";
    lastText = String("HTTP ready: ") + WiFi.localIP().toString();
    lastAudioKey = "";
    redrawDisplay();
    return;
  }

  WiFi.mode(WIFI_AP);
  WiFi.softAP("TetrisChan-Setup");
  Serial.println("WiFi failed. Started AP: TetrisChan-Setup");
  lastExpression = "retort";
  lastText = "WiFi failed. AP: TetrisChan-Setup";
  lastAudioKey = "";
  redrawDisplay();
}

}  // namespace

void setup() {
  Serial.begin(115200);
  M5StackChan.begin();
  M5StackChan.Motion.setAutoAngleSyncEnabled(false);
  motionGoHome(700);
  M5.Display.setRotation(1);
  M5.Display.setTextWrap(true);
  M5.Speaker.setVolume(255);
  cameraReady = CoreS3.Camera.begin();
  Serial.printf("Camera init: %s\n", cameraReady ? "ok" : "failed");

  Serial.println("TetrisChan StackChan HTTP bridge booting");
  connectWiFi();

  server.on("/health", HTTP_GET, []() { replyOk("healthy"); });
  server.on("/action", HTTP_POST, handleAction);
  server.on("/face", HTTP_POST, handleFace);
  server.on("/motion", HTTP_POST, handleMotion);
  server.on("/capture.jpg", HTTP_GET, handleCapture);
  server.on("/capture", HTTP_GET, handleCapture);
  server.on("/last-action", HTTP_GET, handleLastAction);
  server.onNotFound(handleNotFound);
  server.begin();
  Serial.println("HTTP server started");
}

void loop() {
  M5StackChan.update();
  server.handleClient();
  if (isSpeaking && millis() >= nextMouthTick) {
    mouthOpen = !mouthOpen;
    nextMouthTick = millis() + 120;
    redrawDisplay();
  }
  updateMotionTimers();
  releaseAudioBufferIfIdle();
  delay(2);
}
