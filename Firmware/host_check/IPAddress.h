#pragma once
#include "Arduino.h"
class IPAddress { public: uint32_t v = 0; String toString() const; bool operator==(const IPAddress& o) const { return v == o.v; } };
