#pragma once
#include "Arduino.h"
class Preferences { public: bool begin(const char* name, bool readOnly = false, const char* partition = nullptr); void end();
  uint32_t getUInt(const char*, uint32_t = 0); size_t putUInt(const char*, uint32_t);
  String getString(const char*, String = String()); size_t putString(const char*, String);
  float getFloat(const char*, float = 0); size_t putFloat(const char*, float); };
