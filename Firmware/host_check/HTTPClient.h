#pragma once
#include "Arduino.h"
#include "WiFi.h"
class HTTPClient { public: bool begin(String url); bool begin(WiFiClient& client, String url); void setTimeout(uint16_t);
  void addHeader(const String&, const String&); int POST(String payload); int GET(); String getString(); void end(); };
