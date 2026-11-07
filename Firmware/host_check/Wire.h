#pragma once
#include "Arduino.h"
class TwoWire { public: bool begin(int sda, int scl, uint32_t freq); void end(); void beginTransmission(uint16_t);
  uint8_t endTransmission(bool stop = true); size_t write(uint8_t); uint8_t requestFrom(uint16_t, uint8_t); int read(); int available(); };
extern TwoWire Wire;
