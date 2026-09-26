#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include "Display.h"
#if __has_include("secrets.h")
#include "secrets.h"
#endif
#ifndef WIFI_SSID
#define WIFI_SSID "Wokwi-GUEST"
#define WIFI_PASSWORD ""
#endif
#ifndef BACKEND_URL
#define BACKEND_URL "http://host.wokwi.internal:8000/api/v1/display"
#endif
SerialDisplay screen;
uint32_t due = 0;
void setup() {
  Serial.begin(115200);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
}
void loop() {
  if ((int32_t)(millis() - due) < 0) { delay(20); return; }
  due = millis() + 60000; // bounded retry on network/protocol error; backend protects provider
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi unavailable; retry in 60s");
    WiFi.reconnect();
    return;
  }
  HTTPClient http;
  http.setTimeout(5000);
  http.begin(BACKEND_URL);
  int code = http.GET();
  if (code == 200 && http.getSize() <= 4096) {
    String body = http.getString();
    JsonDocument doc;
    if (body.length() <= 4096 && !deserializeJson(doc, body) &&
        doc["version"].as<int>() == 1 && doc["status"].is<const char*>() &&
        doc["retry_after_s"].is<unsigned long>()) {
      unsigned long wait = constrain(doc["retry_after_s"].as<unsigned long>(), 1UL, 86400UL);
      DisplayFrame f = {doc["status"].as<String>(), doc["flight"]["callsign"] | "Unknown",
                        doc["flight"]["origin"] | "???", doc["flight"]["destination"] | "???"};
      screen.show(f);
      due = millis() + wait * 1000UL;
    } else { Serial.println("Invalid response; keeping previous display"); }
  } else { Serial.printf("Backend unavailable: %d\n", code); }
  http.end();
}
