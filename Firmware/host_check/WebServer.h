#pragma once
#include "Arduino.h"
#include "WiFi.h"
#include <functional>
enum HTTPMethod { HTTP_ANY, HTTP_GET, HTTP_POST };
enum HTTPUploadStatus { UPLOAD_FILE_START, UPLOAD_FILE_WRITE, UPLOAD_FILE_END, UPLOAD_FILE_ABORTED };
struct HTTPUpload { HTTPUploadStatus status; String filename; size_t totalSize; size_t currentSize; uint8_t buf[1436]; };
class WebServer { public: typedef std::function<void(void)> THandlerFunction;
  WebServer(int port = 80);
  void on(const String&, HTTPMethod, THandlerFunction); void on(const String&, HTTPMethod, THandlerFunction, THandlerFunction);
  void onNotFound(THandlerFunction); void begin(); void handleClient();
  bool authenticate(const char*, const char*); void requestAuthentication();
  void send(int code, const char* type, const String& content); void send(int code, const char* type, const char* content);
  void sendHeader(const String&, const String&, bool first = false); String arg(const String&); HTTPUpload& upload(); WiFiClient client(); };
