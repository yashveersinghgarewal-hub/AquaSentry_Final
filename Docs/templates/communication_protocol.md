# Communication protocol for an unsafe reading (ISEF items 123, 204)

```
screen positive (≥ 20 µg/L, QC pass)
   │
   ├─► at once: operator tells the source owner / caretaker in plain words:
   │     "Arsenic was detected. This is a screening result. Please do not drink from this source until a laboratory confirms. Use <alternative source>."
   ├─► same day: split sample to the district laboratory (sample code on both bottles); log who was told and when
   ├─► within 48 h: district water-quality officer informed (JJM export or PDF certificate); panchayat informed if the lab confirms
   └─► result returns:
         confirmed ≥ 10 µg/L → authority acts (marking, alternative supply); device result recorded as confirmed
         < 10 µg/L            → tell the owner; record as a screening false positive; review the node

retest (borderline)
   └─► repeat the test; send a split to the laboratory; advise caution until the result returns

invalid (QC fail)
   └─► repeat after the suggested action; never report a number
```

Decide who holds each role before the first field day; write names and phone numbers in the logbook, not in the repository.
