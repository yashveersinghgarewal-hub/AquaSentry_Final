# Host compile check for the ESP32 sketch

These are **minimal stand-ins** for the Arduino-ESP32 core headers (same function names and
argument types as the real core). They let a normal PC compiler type-check
`esp32_firmware.ino` and link it against the AquaNet C engines, so typos, wrong signatures and
C/C++ linkage mistakes are caught by `python main.py --test` without installing the ESP32 toolchain.

They do **not** replace a real build: the GitHub Actions job `firmware` compiles the sketch with
Espressif's own core for ESP32, ESP32-S3 and ESP32-C3. When you add a call to a core function the
stubs do not know, add a matching declaration here.
