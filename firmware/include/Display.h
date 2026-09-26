#pragma once
#include <Arduino.h>
struct DisplayFrame { String status, callsign, origin, destination; };
class Display {
public:
  virtual ~Display() = default;
  virtual void show(const DisplayFrame &frame) = 0;
};
class SerialDisplay final : public Display {
public:
  void show(const DisplayFrame &f) override {
    Serial.printf("DISPLAY %s | %s | %s -> %s\n", f.status.c_str(), f.callsign.c_str(), f.origin.c_str(), f.destination.c_str());
  }
};
// Future WaveshareEpaperDisplay implements Display. No pins or panel selected yet.
