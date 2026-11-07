#pragma once
#include "Arduino.h"
enum SeekMode { SeekSet = 0, SeekCur = 1, SeekEnd = 2 };
class File { public: size_t write(const uint8_t*, size_t); size_t read(uint8_t*, size_t); bool seek(uint32_t, SeekMode); size_t size() const; void close(); operator bool() const; };
