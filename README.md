# Mall Parking System — Skeleton

A working end-to-end skeleton: live camera preview → click "Detect" → plate
recognized → DB lookup → auto WhatsApp / manual entry / print receipt →
slot assignment. Exit flow frees the slot.

## How to run

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # on Windows: venv\Scripts\activate
pip install -r requirements.txt
python database.py             # creates parking.db with sample data
uvicorn main:app --reload --port 8000
```

Then open **http://localhost:8000** in your browser (Chrome/Edge recommended
for camera access). Allow camera permission when prompted.

- Click **"Detect (Entry)"** — it will detect the plate in the current frame.
  Right now `anpr.py` is a *stub* that always returns a fixed test plate
  `OD02AB1234`, which is already seeded as "registered" in the database
  with a mobile number — so you'll see the auto-WhatsApp (logged to your
  terminal) path immediately.
- Click **"Detect (Exit)"** — frees up the slot for that plate.
- The **Slots** panel shows live occupied/free status.

## What to plug in next

| File | What to do |
|---|---|
| `backend/anpr.py` | Replace the stub in `detect_plate()` with a call to your existing Python ANPR model. It receives raw image bytes and must return the plate string (or `None`). |
| `backend/notify.py` | Replace `send_whatsapp()` with a real WhatsApp Business API call (Twilio/Gupshup/Meta Cloud API — see comments in the file for a Twilio example). |
| `backend/notify.py` | Replace `print_receipt()` with a real call to your receipt printer (see `python-escpos` example in the comments). This must run **on the gate PC itself**, since the printer is physically local. |
| `backend/database.py` | Swap SQLite for PostgreSQL/MySQL when you're ready for production — the schema and queries barely change. |

## Multi-gate / multi-screen

- Every gate PC just opens the same `index.html` in a browser (kiosk mode
  recommended), pointed at the central backend's URL.
- Change the `GATE_ID` constant at the top of `index.html`'s `<script>`
  block to a unique value per gate (e.g. `gate_1`, `gate_2`).
- All gates share the same central database/backend, so slot availability
  and vehicle records stay consistent across the whole mall.
- To run on gate PCs on a local network, replace `http://localhost:8000`
  in `index.html` with the backend server's actual IP/hostname.

## Architecture recap

```
Browser (per gate)                 FastAPI Backend                 SQLite/Postgres DB
------------------                 ----------------                -------------------
Live cam preview (JS)
  |
  v
Click "Detect"
  |
  v
Capture 1 frame  ---image--->   /entry/detect
                                   |-- anpr.detect_plate()
                                   |-- lookup vehicle in DB  <---------------->
                                   |-- find free slot        <---------------->
                                   |-- registered? -> send_whatsapp() + assign slot
                                   |-- not? -> return "unregistered" + suggested slot
  <--- response ---
Show popup (if unregistered)
  |
  v
Gatekeeper picks: enter mobile -> /entry/confirm
                  OR print     -> /entry/print
```
