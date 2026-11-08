#pragma once
#include "WiFi.h"
typedef enum { HTTP_UPDATE_FAILED, HTTP_UPDATE_NO_UPDATES, HTTP_UPDATE_OK } t_httpUpdate_return;
class HTTPUpdate { public: void rebootOnUpdate(bool); t_httpUpdate_return update(WiFiClient& client, const String& url,
  const String& currentVersion = ""); String getLastErrorString(); };
extern HTTPUpdate httpUpdate;
