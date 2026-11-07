#pragma once
#include "Arduino.h"
class HTTPClient { public: bool begin(String url); void setTimeout(uint16_t); void addHeader(const String&, const String&); int POST(String payload); void end(); };
