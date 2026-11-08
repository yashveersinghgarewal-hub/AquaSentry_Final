#pragma once
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cctype>
#include <cmath>
#include <ctime>
#include <string>
using std::isnan;
#define F(x) (x)
#define HIGH 1
#define LOW 0
#define INPUT 0x01
#define OUTPUT 0x03
#define INPUT_PULLUP 0x05
#define OUTPUT_OPEN_DRAIN 0x13
typedef bool boolean;
class String {
public:
  std::string s;
  String(const char* c = "") : s(c ? c : "") {}
  String(const std::string& x) : s(x) {}
  explicit String(int v) : s(std::to_string(v)) {}
  explicit String(unsigned long v) : s(std::to_string(v)) {}
  String(float v, unsigned int dec) { char b[32]; snprintf(b, sizeof b, "%.*f", (int)dec, v); s = b; }
  const char* c_str() const { return s.c_str(); }
  unsigned int length() const { return (unsigned)s.size(); }
  bool startsWith(const char* p) const { return s.rfind(p, 0) == 0; }
  void trim() {}
  char operator[](unsigned int i) const { return s[i]; }
  String& operator+=(const String& o) { s += o.s; return *this; }
  String& operator+=(const char* o) { s += o; return *this; }
  String& operator+=(char c) { s += c; return *this; }
  friend String operator+(const String& a, const String& b) { return String(a.s + b.s); }
  friend String operator+(const String& a, const char* b) { return String(a.s + b); }
  friend String operator+(const char* a, const String& b) { return String(std::string(a) + b.s); }
  int indexOf(const String& k) const { auto i = s.find(k.s); return i == std::string::npos ? -1 : (int)i; }
  int indexOf(char c, unsigned int from = 0) const { auto i = s.find(c, from); return i == std::string::npos ? -1 : (int)i; }
  String substring(unsigned int a, unsigned int b) const { return String(s.substr(a, b - a)); }
  String substring(unsigned int a) const { return String(s.substr(a)); }
  bool startsWith(const String& p) const { return s.rfind(p.s, 0) == 0; }
  bool operator==(const String& o) const { return s == o.s; }
  bool operator==(const char* o) const { return s == o; }
  bool operator!=(const String& o) const { return s != o.s; }
  bool operator!=(const char* o) const { return s != o; }
};
class Print { public: virtual ~Print() {} };
class HardwareSerial : public Print {
public:
  void begin(unsigned long) {}
  int printf(const char*, ...) __attribute__((format(printf, 2, 3)));
  size_t println(const char*); size_t println(); void flush();
};
extern HardwareSerial Serial;
void pinMode(uint8_t, uint8_t); void digitalWrite(uint8_t, uint8_t); int digitalRead(uint8_t);
uint16_t analogRead(uint8_t); void analogReadResolution(uint8_t); uint32_t analogReadMilliVolts(uint8_t);
#define RTC_DATA_ATTR
void delay(uint32_t); void delayMicroseconds(uint32_t); unsigned long millis();
void configTime(long gmtOffset_sec, int daylightOffset_sec, const char* s1, const char* s2 = nullptr, const char* s3 = nullptr);
class EspClass { public: void restart(); uint32_t getFreeHeap(); };
extern EspClass ESP;
/* FreeRTOS */
typedef void* QueueHandle_t; typedef void* SemaphoreHandle_t; typedef void* TaskHandle_t;
typedef int BaseType_t; typedef unsigned int UBaseType_t; typedef uint32_t TickType_t;
#define pdTRUE 1
#define pdPASS 1
#define portTICK_PERIOD_MS 1
#define portMAX_DELAY 0xffffffffUL
QueueHandle_t xQueueCreate(UBaseType_t, UBaseType_t);
BaseType_t xQueueReceive(QueueHandle_t, void*, TickType_t);
BaseType_t xQueueSend(QueueHandle_t, const void*, TickType_t);
UBaseType_t uxQueueMessagesWaiting(QueueHandle_t);
SemaphoreHandle_t xSemaphoreCreateMutex();
void vTaskDelay(TickType_t);
BaseType_t xTaskCreatePinnedToCore(void (*)(void*), const char*, uint32_t, void*, UBaseType_t, TaskHandle_t*, BaseType_t);
