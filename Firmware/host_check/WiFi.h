#pragma once
#include "Arduino.h"
#include "IPAddress.h"
typedef enum { WIFI_OFF = 0, WIFI_STA = 1, WIFI_AP = 2, WIFI_AP_STA = 3 } wifi_mode_t;
#define WL_CONNECTED 3
class WiFiClient { public: IPAddress localIP(); };
class WiFiClass { public: bool mode(wifi_mode_t); int begin(const char* ssid, const char* pass); int status();
  bool setAutoReconnect(bool); IPAddress localIP(); int8_t RSSI(); uint8_t* macAddress(uint8_t* mac);
  bool softAP(const char* ssid, const char* pass = nullptr); IPAddress softAPIP(); uint8_t softAPgetStationNum(); };
extern WiFiClass WiFi;
