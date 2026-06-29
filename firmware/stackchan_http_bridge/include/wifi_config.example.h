#pragma once

// Copy this file to wifi_config.h and fill in your Wi-Fi credentials.
// wifi_config.h is ignored by git.

#define WIFI_SSID "YOUR_WIFI_SSID"
#define WIFI_PASSWORD "YOUR_WIFI_PASSWORD"

// Keep StackChan on the address used by the Python sender.
#define STACKCHAN_STATIC_IP "192.168.11.15"
#define STACKCHAN_GATEWAY_IP "192.168.11.1"
#define STACKCHAN_SUBNET_IP "255.255.255.0"
#define STACKCHAN_DNS_IP "192.168.11.1"

// Optional: bridge used when action.audio.path is "/audio/<key>.wav".
#define AUDIO_BASE_URL "http://192.168.0.10:8787"

// Keep failed WAV fetches silent during the demo.
#define ENABLE_FEEDBACK_TONE 0
