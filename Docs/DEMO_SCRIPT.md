# 60-second software demo — click path

ISEF items 195, 200: three screens, no chatbot, no market pages. Switch **judging mode** on (the podium icon in the
top bar, or open `index.html?mode=judging`) before judges arrive. Words are yours; this is only the path.

| Time | Screen | Click | What to point at |
|---|---|---|---|
| 0–15 s | **Overview** | (already open) | The outcome chip (*not detected / retest / screen positive / invalid*), the value **x ± U µg/L**, the mode badge (live / replay / simulation), the data age. "The sensor sees from 20 µg/L; the legal limit is 10; the chip says what we can and cannot conclude." |
| 15–35 s | **Test a sample** | *Replay a recorded scan* → pick a real instrument file | The raw trace, the baseline, the peak at −800 mV, the QC flags; then *View stored scan* → the checksum. "Every number is tied to its scan; a bad scan fails, it never becomes a number." |
| 35–55 s | **Devices & history** | the lab-confirmation panel | Node value next to the laboratory value with the pairing by sample code; the fleet list with outcomes per source. |
| 55–60 s | **Report** | *PDF* | The certificate: outcome first, uncertainty, calibration ID, firmware, analysis version. |

If the server is down: the dashboard still runs the same pipeline in the browser (asv.js) and says so; the printed
figures on the poster do not depend on it (item 10).
