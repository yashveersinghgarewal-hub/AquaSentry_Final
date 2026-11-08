#pragma once
#include "FS.h"
class LittleFSFS { public: bool begin(bool formatOnFail = false, const char* basePath = "/littlefs", uint8_t maxOpenFiles = 10, const char* label = "spiffs");
  File open(const char* path, const char* mode = "r", bool create = false); bool remove(const char* path); bool rename(const char* from, const char* to); };
extern LittleFSFS LittleFS;
