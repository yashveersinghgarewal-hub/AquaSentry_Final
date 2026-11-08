# AquaSentry Home: Hardware Assembly Manual
## Complete Step-by-Step Guide to Building the In-Tank Water Quality & Arsenic Surveillance Sentry

---

### Executive Overview

This manual provides complete, beginner-friendly, step-by-step instructions to build, wire, test, and install the **AquaSentry Home** prototype. 

AquaSentry Home is a dedicated surveillance node installed inside a domestic overhead water storage tank (e.g. Sintex 500L / 1000L). It monitors continuous water parameters (TDS, pH, Turbidity, Temperature), performs automated daily electrochemical Anodic Stripping Voltammetry (ASV) tests for trace dissolved Arsenic ($As^{3+}$), and runs the on-device **AquaNet-V1** neural network to provide real-time potability verdicts to your smartphone over Wi-Fi.

---

### Workshop Tools & Consumables Required

Before starting, ensure you have the following basic tools:

| Tool / Consumable | Recommended Specification | Purpose |
| :--- | :--- | :--- |
| **Soldering Iron & Solder** | 40W–60W temperature-controlled, 60/40 leaded or lead-free solder | Making reliable electrical connections |
| **Digital Multimeter (DMM)** | Standard multimeter with DC voltage & continuity buzzer mode | Testing voltages and verifying zero short circuits |
| **Wire Strippers & Cutters** | 20–30 AWG wire strippers, flush cutters | Trimming and stripping silicone hookup wire |
| **Heat Shrink Tubing & Lighter / Heat Gun** | 1.5mm, 2.5mm, 4.0mm heat shrink sleeves | Insulating soldered splice joints against tank humidity |
| **Screwdriver Set** | Small Phillips (PH0, PH1) & 2.0mm / 2.5mm Allen keys | Securing M3 screws and PCB standoffs |
| **Silicone Sealant / RTV** | Neutral-cure clear silicone sealant (food-contact safe) | Hermetic waterproofing of cable gland entries |
| **Breadboard / Perfboard** | 4cm x 6cm standard double-sided prototype perfboard | Soldering voltage divider resistors & op-amp circuit |

---

### Complete Bill of Materials (BOM) & Parts Checklist

Check off each item before beginning assembly:

```
[ ] 1x ESP32 DevKit V1 (30-pin, Dual-Core 240MHz with Wi-Fi)
[ ] 1x ADS1115 16-Bit 4-Channel I2C ADC Module
[ ] 1x MCP6002 Rail-to-Rail Dual CMOS Op-Amp (DIP-8 or breakout module)
[ ] 1x Screen-Printed Gold 3-Electrode Strip (MAS-G1 or DropSens Gold WE, Ag/AgCl RE, Carbon CE)
[ ] 1x 12V DC Micro Peristaltic Dosing Pump (with silicone hose barbs)
[ ] 1x IRLZ44N Logic-Level N-Channel MOSFET (TO-220 package or breakout board)
[ ] 1x 1N4007 Diode (motor inductive flyback suppression)
[ ] 1x DS18B20 Waterproof Stainless Steel Temperature Probe (with 1-meter cable)
[ ] 1x Analog TDS / Electrical Conductivity Sensor Module (Gravity-style probe + board)
[ ] 1x Analog Optical Turbidity Sensor Module (IR sensor head + adapter board)
[ ] 1x Analog pH Sensor Kit (E-201-C glass composite probe + 4502C conditioning board)
[ ] 1x 12V 2A Regulated DC Power Adapter (wall plug with 5.5mm x 2.1mm DC barrel jack)
[ ] 1x LM2596 DC-DC Step-Down Buck Converter Module (with onboard adjustment trimmer)
[ ] 1x WS2812B NeoPixel RGB LED Ring (8 LEDs, 5V)
[ ] 1x Active 5V Piezo Buzzer
[ ] 2 Meters Food-Grade Silicone Tubing (2mm Inner Diameter / 4mm Outer Diameter)
[ ] Resistors: 1x 4.7kΩ (for DS18B20), 1x 10kΩ (MOSFET gate pull-down), 1x 10kΩ + 1x 20kΩ (Turbidity divider)
[ ] 3D-Printed Parts: Enclosure Base & Lid, Rim Clamp Bracket, 15 mL Stripping Chamber (PETG)
[ ] Fasteners: 8x M3x10mm stainless screws, 4x M3 brass threaded heat-set inserts, 1x 70mm silicone O-ring
```

---

## Step 1: 3D Printing & Mechanical Preparation

AquaSentry Home lives in the high-humidity headspace of a domestic water tank. Material selection and print settings are critical:

1. **Filament Choice**: 
   * **Print exclusively with PETG** (Food-contact safe, zero BPA, chemical-resistant to chlorine, heat resistant to $75^\circ\text{C}$). 
   * *Do NOT use PLA* (PLA softens under rooftop solar heat at $55^\circ\text{C}$ and degrades in high humidity).
2. **Slicer Settings**:
   * Layer Height: **0.20 mm**
   * Perimeters (Wall loops): **4 walls minimum** (essential for watertight layer bonding).
   * Infill: **40% Gyroid infill**.
   * Top & Bottom Layers: **5 solid layers**.
3. **Heat-Set Insert Installation**:
   * Using a soldering iron heated to $220^\circ\text{C}$, gently press the four **M3 brass threaded inserts** into the pre-modeled mounting posts of the main enclosure base until flush with the plastic rim.
4. **Fit the Silicone O-Ring**:
   * Stretch the 70mm silicone O-ring into the circumferential sealing groove on the upper rim of the main housing. Apply a very thin bead of silicone grease to preserve elasticity.

---

## Step 2: Power Subsystem Calibration & Assembly

> [!CAUTION]
> You must adjust the LM2596 step-down voltage with a multimeter **BEFORE** connecting the ESP32 or any sensor. Feeding raw 12V into the 5V pins will permanently destroy the electronics!

```
[12V 2A DC Jack] ──┬─────────────────────────────> [12V (+) Pump Power Rail]
                   │
                   └──> [LM2596 Buck Converter IN+]
                        Trimmer Pot tuned to 5.05V
                        [LM2596 Buck Converter OUT+] ──> [Clean 5V Rail for ESP32 & Sensors]
```

1. **Connect 12V Input**:
   * Solder the female DC barrel jack connector to the `IN+` and `IN-` terminals of the **LM2596 buck converter**.
   * Plug in the 12V 2A wall adapter.
2. **Voltage Calibration**:
   * Set your digital multimeter to **DC Volts (20V range)**.
   * Place the black probe on `OUT-` and the red probe on `OUT+` of the LM2596.
   * Using a small precision flathead screwdriver, slowly turn the brass screw on the blue potentiometer:
     * Counter-clockwise lowers the voltage.
     * Rotate until the multimeter reads exactly **$5.05\text{ V}$** (this accounts for small voltage drops across wiring).
3. **Disconnect Power**:
   * Unplug the 12V adapter from the wall before proceeding.
4. **Create the Common Power Rails**:
   * Solder a 3-wire distribution bus on your mini perfboard:
     * **12V Rail (Yellow/Red wire)**: Feeds the peristaltic pump (+) terminal.
     * **5V Rail (Red wire)**: Feeds ESP32 `VIN`, 4502C pH board VCC, Turbidity board VCC, and NeoPixel VCC.
     * **Common Ground Rail (Black wire)**: Connect all subsystem grounds together (LM2596 `OUT-`, ESP32 `GND`, sensor grounds, and MOSFET source pin).

---

## Step 3: Preparing the Analog Core & Precision ADC

The ESP32's built-in ADC has non-linearity issues near 0V and 3.3V. The **ADS1115 module** provides precision 16-bit analog conversion across the entire range.

```
       ESP32 DevKit V1                 ADS1115 16-Bit ADC
   ┌─────────────────────┐            ┌──────────────────┐
   │         3.3V Output ├───────────>│ VDD              │
   │                 GND ├───────────>│ GND              │
   │    GPIO 21 (I2C SDA)├───────────>│ SDA              │
   │    GPIO 22 (I2C SCL)├───────────>│ SCL              │
   │                     │            │ ADDR (to GND)    │
   └─────────────────────┘            │                  │
                                      │ A0 ──> Arsenic Op-Amp (MCP6002)
                                      │ A1 ──> TDS Probe Output
                                      │ A2 ──> Turbidity (Divided to 3V)
                                      │ A3 ──> pH Board (Po Output)
                                      └──────────────────┘
```

1. **Powering ADS1115**:
   * Solder a wire from the **ESP32's 3.3V pin** to the ADS1115 **VDD** pin.
   * *Why 3.3V?* This forces the ADS1115's $I^2C$ communication lines to operate strictly at 3.3V, matching the ESP32's logic level with **zero logic level shifters needed**.
2. **Connect the I2C Bus**:
   * Solder ADS1115 **SDA** to ESP32 **GPIO 21**.
   * Solder ADS1115 **SCL** to ESP32 **GPIO 22**.
   * Solder ADS1115 **ADDR** pin to ADS1115 **GND** (this sets the default $I^2C$ bus address to `0x48`).
3. **Assemble the MCP6002 Potentiostat Circuit**:
   * Mount the **MCP6002 dual rail-to-rail op-amp** on the mini perfboard.
   * Power MCP6002 $V_{DD}$ (Pin 8) from ESP32 3.3V and $V_{SS}$ (Pin 4) to Common GND.
   * Connect ESP32 **GPIO 25 (Internal DAC 1)** to the non-inverting input of Op-Amp 1 through a $10\text{k}\Omega / 2.2\text{k}\Omega$ voltage divider. This allows the ESP32 to generate the Anodic Stripping Voltammetry potential ramp ($-0.8\text{V}$ to $+0.4\text{V}$ relative to reference).
   * Connect the Working Electrode (WE) through the Transimpedance Amplifier (Op-Amp 2) to convert stripping nano-amp currents to micro-volts.
   * Connect the output of Op-Amp 2 to **ADS1115 Channel A0**.

---

## Step 4: Arsenic Stripping Cell & Pump Fluidics

Leaving the gold electrode permanently submerged in domestic water causes biofouling within 48 hours. The peristaltic pump draws $15\text{ mL}$ for testing once a day, then purges the chamber dry.

```
                  +12V Supply Rail
                         │
                         ├──[1N4007 Diode]──┐ (Cathode Stripe to +12V)
                         │                  │
                    ┌────┴────┐             │
                    │ 12V DC  │             │
                    │ Perist. │             │
                    │  Pump   │             │
                    └────┬────┘             │
                         │                  │
                         ├──────────────────┘
                         │
                      [Drain]
      ESP32 GPIO 18 ──[Gate ] IRLZ44N N-Channel MOSFET
      (with 10k to GND)│
                      [Source]
                         │
                    [Common GND]
```

1. **Install Flyback Diode Across Pump Terminals**:
   * Solder a **1N4007 diode** directly across the pump's two DC terminals.
   * **Orientation**: The side of the diode with the silver stripe (cathode) **must connect to the positive (+12V) terminal**. This absorbs reverse inductive flyback spikes when the pump stops.
2. **Wire the IRLZ44N MOSFET Switch**:
   * Pin 1 (Gate): Solder a $10\text{ k}\Omega$ resistor between Gate and Common GND (pull-down). Solder Gate to ESP32 **GPIO 18**.
   * Pin 2 (Drain): Solder to the **negative ($-$) terminal** of the peristaltic pump.
   * Pin 3 (Source): Solder directly to the **Common GND** rail.
   * Connect the positive ($+$) terminal of the pump to the **+12V rail**.
3. **Plumbing the Silicone Tubing**:
   * Cut a 40 cm length of $2\text{ mm ID} / 4\text{ mm OD}$ food-grade silicone tubing for the suction line.
   * Push one end onto the pump inlet barb. Push the other end through the bottom cable gland of the enclosure down into the water tank.
   * Connect a 10 cm piece of tubing from the pump outlet barb into the inlet port of the 3D-printed $15\text{ mL}$ stripping chamber.
   * Slide the **screen-printed gold electrode strip** into the chamber slot, ensuring the silicone gasket seals tightly against the electrode edges.
   * Connect a discharge tube from the chamber outlet port leading back to the tank drain.

---

## Step 5: Auxiliary Water Quality Probes & Resistor Conditioning

Now wire the remaining 4 auxiliary sensors to provide complete geochemical context for AquaNet:

```
  ┌────────────────────────────────────────────────────────┐
  │ SENSOR WIRING & VOLTAGE CONDITIONING MATRIX            │
  ├───────────────────┬──────────────┬──────────┬──────────┤
  │ Sensor Probe      │ Power (VCC)  │ Ground   │ Signal   │
  ├───────────────────┼──────────────┼──────────┼──────────┤
  │ DS18B20 Temp      │ 3.3V (ESP32) │ GND      │ GPIO 4   │
  │ TDS Conductivity  │ 3.3V (ESP32) │ GND      │ ADS1115 A1
  │ Optical Turbidity │ 5.0V (Buck)  │ GND      │ ADS1115 A2*
  │ pH Probe (4502C)  │ 5.0V (Buck)  │ GND      │ ADS1115 A3
  └───────────────────┴──────────────┴──────────┴──────────┘
  * Note: Turbidity signal passes through 10k/20k voltage divider!
```

### 1. DS18B20 Temperature Probe
* Red Wire $\to$ ESP32 **3.3V**.
* Black Wire $\to$ Common **GND**.
* Yellow Wire (Data) $\to$ ESP32 **GPIO 4**.
* **Crucial Resistor**: Solder a **$4.7\text{ k}\Omega$ resistor** between the Yellow Data wire and 3.3V (1-Wire pull-up).

### 2. Analog TDS Probe
* VCC $\to$ ESP32 **3.3V**.
* GND $\to$ Common **GND**.
* Analog Signal Pin $\to$ **ADS1115 Channel A1**.

### 3. Optical Turbidity Sensor (Voltage Divider Conditioning)
* The optical turbidity board requires $5\text{V}$ VCC. In clear water, its output is **$4.1\text{V} - 4.5\text{V}$**, which would damage the 3.3V ADC.
* Solder the **$10\text{ k}\Omega$ and $20\text{ k}\Omega$ voltage divider** on your perfboard:
  ```
  Turbidity Signal Pin ──>[ 10 kΩ ]──┬──> Connect to ADS1115 A2 (Max 3.0V)
                                     │
                                  [ 20 kΩ ]
                                     │
                                    GND
  ```
* Connect VCC to the **5V rail**, GND to **Common GND**, and the center tap between the two resistors to **ADS1115 Channel A2**.

### 4. Analog pH Sensor Board (4502C)
* Connect VCC to the **5V rail** (pH glass probes require 5V reference amplifiers).
* Connect GND to **Common GND**.
* Connect the analog output pin ($Po$) directly to **ADS1115 Channel A3**.
* Connect the BNC connector of the glass electrode probe securely to the BNC jack on the board.

---

## Step 6: Status Ring, Buzzer & Enclosure Assembly

```
  ESP32 DevKit V1                 Alert Peripherals
┌─────────────────┐             ┌─────────────────────┐
│    GPIO 5 (Out) ├────────────>│ NeoPixel DIN (Pin 1)│
│    GPIO 19(Out) ├────────────>│ Piezo Buzzer (+)    │
│    5.0V Supply  ├────────────>│ NeoPixel 5V (Pin 2) │
│    Common GND   ├────────────>│ NeoPixel GND & Buzz-│
└─────────────────┘             └─────────────────────┘
```

1. **WS2812B NeoPixel 8-LED Ring**:
   * Mount the LED ring directly under the clear acrylic dome on the top lid.
   * Solder LED `+5V` to the **5V rail**.
   * Solder LED `GND` to **Common GND**.
   * Solder LED `DIN` to ESP32 **GPIO 5**.
2. **Active 5V Piezo Buzzer**:
   * Solder Buzzer $(+)$ pin to ESP32 **GPIO 19**.
   * Solder Buzzer $(-)$ pin to **Common GND**.
3. **Internal Wire Dress**:
   * Use small zip-ties to bundle the low-voltage sensor cables away from the 12V pump power wires to minimize electrical noise coupling into the ADC.
4. **Final Closure**:
   * Carefully position the electronics tray into the 3D-printed PETG base.
   * Place the clear top lid over the silicone O-ring gasket.
   * Tighten the four **M3x10mm stainless steel screws** in an alternating cross-pattern until the O-ring visibly compresses by approximately $30\%$.

---

## Step 7: Benchtop Pre-Flight Check & Firmware Flashing

Before installing in the tank, perform this 5-minute electrical verification on your workbench:

### 1. The "Smoke-Test" (Continuity & Resistance Check)
* Set multimeter to **Continuity Buzzer mode**.
* Test between:
  * 12V rail and GND: **Must NOT beep** (no short).
  * 5V rail and GND: **Must NOT beep**.
  * 3.3V rail and GND: **Must NOT beep**.
* If any rail beeps, find and fix the solder bridge before applying power!

### 2. Flashing the Firmware
* Connect the ESP32 to your computer using a Micro-USB or USB-C data cable.
* In the Arduino IDE or PlatformIO:
  * Select Board: **ESP32 Dev Module** (CPU Frequency: 240MHz).
  * Copy the verified ANSI C99 files: [`Neural_Network/aquanet_v1.h`](../../Neural_Network/aquanet_v1.h) and [`Neural_Network/aquanet_v1.c`](../../Neural_Network/aquanet_v1.c) into your project's `src/` directory.
  * Enter your home 2.4 GHz Wi-Fi SSID and Password in `config.h`.
  * Click **Upload**.
* Open the Serial Monitor at **115200 baud**. You should observe:
  ```text
  [AquaSentry Home] Booting ESP32 Dual-Core Core...
  [AquaNet-V1] Initializing 23-node 112-synapse neural engine... OK.
  [ADS1115] Initializing 16-bit I2C ADC at 0x48... FOUND.
  [DS18B20] Dallas 1-Wire temperature sensor... FOUND (24.2 C).
  [Wi-Fi] Connected to Home Network. Local IP: 192.168.1.145
  [mDNS] Web server responder active at http://aquasentry.local
  [NeoPixel] Self-test complete: Glowing Green.
  ```

---

## Step 8: Tank Installation & Daily Operation

1. **Mounting on the Water Tank**:
   * Open the overhead water tank inspection manhole (e.g. Sintex tank top lid).
   * Hook the 3D-printed PETG rim clamp over the tank lip and tighten the thumbscrew.
   * The main enclosure stays **outside/above the waterline** in the dome headspace.
2. **Submerging the Probe Harness**:
   * Lower the probe bracket (holding TDS, pH, Temp, and the silicone suction tube) into the water column until it rests **30–50 cm below the surface**.
   * *Ensure the suction tube tip is at least 15 cm above the tank bottom* to avoid pulling settled sediment into the sampling cell.
3. **Plugging In**:
   * Route the 12V DC power cable to the nearest electrical socket (typically the rooftop water pump starter switchboard or bathroom geyser socket).
4. **Accessing Your Dashboard**:
   * On your smartphone, tablet, or laptop connected to your home Wi-Fi, open your browser and navigate to:
     ```text
     http://aquasentry.local
     ```
   * *(Or type the ESP32's assigned IP address, e.g. `http://192.168.1.145`).*
   * You will see the real-time hydrogeochemical dashboard displaying:
     * **Arsenic**: Measured stripping concentration ($mg/L$).
     * **pH & TDS**: Acidity and mineral content.
     * **Turbidity**: Water clarity (alerts if tank cleaning is due).
     * **Neural Potability Status**:
       * 🟢 **Safe**: Arsenic $< 0.010\text{ mg/L}$, all parameters within WHO standards.
       * 🟡 **Caution**: Exceeds WHO guideline, within domestic limits.
       * 🔴 **Unsafe**: Exceeds BIS 10500 permissible limit ($> 0.050\text{ mg/L}$). Alarm sounds.

---

## Troubleshooting Quick-Reference

| Symptom | Probable Cause | Fix |
| :--- | :--- | :--- |
| **ESP32 does not power on** | LM2596 buck voltage not reaching VIN | Check DC adapter connection; verify LM2596 outputs 5.0V with multimeter. |
| **Serial monitor reports `ADS1115 NOT FOUND`** | Loose I2C wiring or incorrect VDD voltage | Verify SDA $\to$ GPIO 21, SCL $\to$ GPIO 22, and VDD is on 3.3V (not 5V). |
| **Pump clicks but doesn't spin** | Gate threshold not reached (IRF520 used instead of IRLZ44N) | Replace with a logic-level IRLZ44N MOSFET; verify 12V rail has power. |
| **Temperature reads -127°C** | 1-Wire pull-up resistor missing or disconnected | Solder a $4.7\text{ k}\Omega$ resistor between DS18B20 Data (Yellow) and 3.3V. |
| **Arsenic stripping peak is noisy** | Motor noise or ground loop coupling | Verify 1N4007 flyback diode is across pump; ensure common ground is solid. |
| **Wi-Fi cannot connect** | 5 GHz network selected (ESP32 only supports 2.4 GHz) | Connect smartphone to router's 2.4 GHz band and enter credentials. |

---

### Congratulations!
Your **AquaSentry Home** autonomous surveillance node is now fully assembled, calibrated, and guarding your household drinking water with edge-grade neural precision.
