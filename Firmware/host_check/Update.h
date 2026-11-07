#pragma once
#include "Arduino.h"
#define UPDATE_SIZE_UNKNOWN 0xFFFFFFFF
class UpdateClass { public: bool begin(size_t size = UPDATE_SIZE_UNKNOWN); size_t write(uint8_t*, size_t); bool end(bool evenIfRemaining = false);
  bool hasError(); void printError(Print&); };
extern UpdateClass Update;
