"""
Mall Parking System — Backend API

Run with:
    uvicorn main:app --reload --port 8000

Endpoints:
    POST /entry/detect   -> capture frame, detect plate, check DB, decide next step
    POST /entry/confirm  -> gatekeeper manually enters mobile + confirms send
    POST /entry/print    -> gatekeeper chooses "print receipt" instead
    POST /exit/detect    -> capture frame, detect plate, free up the slot
    GET  /slots          -> current slot status (for the UI to display)
"""

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from datetime import datetime
from fastapi.concurrency import run_in_threadpool

from database import get_connection, init_db
from anpr import detect_plate
from notify import send_whatsapp, print_receipt

app = FastAPI(title="Mall Parking System")

# Allow the frontend (served separately or via file://) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()


def find_free_slot(gate_id: str):
    conn = get_connection()
    row = conn.execute(
        "SELECT slot_id FROM slots WHERE status = 'free' LIMIT 1"
    ).fetchone()
    conn.close()
    return row["slot_id"] if row else None


def assign_slot(plate_number: str, slot_id: str, gate_id: str):
    conn = get_connection()
    conn.execute("UPDATE slots SET status = 'occupied' WHERE slot_id = ?", (slot_id,))
    conn.execute(
        """INSERT INTO parking_sessions (plate_number, slot_id, gate_in, entry_time, status)
           VALUES (?, ?, ?, ?, 'active')""",
        (plate_number, slot_id, gate_id, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()

def lookup_vehicle(plate_number: str):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM vehicles WHERE plate_number = ?", (plate_number,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


@app.post("/entry/detect")
async def entry_detect(gate_id: str = Form(...), image: UploadFile = File(...)):
    image_bytes = await image.read()
    plate_number = await run_in_threadpool(detect_plate, image_bytes)
    
    

    if not plate_number:
        return {"status": "no_plate_detected"}

    vehicle = lookup_vehicle(plate_number)
    slot_id = find_free_slot(gate_id)

    if not slot_id:
        return {"status": "full", "plate_number": plate_number}

    if vehicle and vehicle.get("mobile_number"):
        # Registered vehicle -> auto slot assign + auto WhatsApp
        assign_slot(plate_number, slot_id, gate_id)
        send_whatsapp(
            vehicle["mobile_number"],
            f"Welcome! Your vehicle {plate_number} is parked at slot {slot_id}.",
        )
        return {
            "status": "registered",
            "plate_number": plate_number,
            "slot_id": slot_id,
            "mobile_number": vehicle["mobile_number"],
        }
    else:
        # Unregistered -> gatekeeper must choose: enter mobile OR print receipt
        # Slot is reserved now so two cars can't grab it while the gatekeeper decides
        return {
            "status": "unregistered",
            "plate_number": plate_number,
            "suggested_slot_id": slot_id,
        }


@app.post("/entry/confirm")
async def entry_confirm(
    plate_number: str = Form(...),
    mobile_number: str = Form(...),
    slot_id: str = Form(...),
    gate_id: str = Form(...),
):
    # Save mobile number against the plate for next time, assign slot, notify
    conn = get_connection()
    conn.execute(
        """INSERT INTO vehicles (plate_number, mobile_number) VALUES (?, ?)
           ON CONFLICT(plate_number) DO UPDATE SET mobile_number = excluded.mobile_number""",
        (plate_number, mobile_number),
    )
    conn.commit()
    conn.close()

    assign_slot(plate_number, slot_id, gate_id)
    send_whatsapp(
        mobile_number,
        f"Welcome! Your vehicle {plate_number} is parked at slot {slot_id}.",
    )
    return {"status": "confirmed", "slot_id": slot_id}


@app.post("/entry/print")
async def entry_print(
    plate_number: str = Form(...),
    slot_id: str = Form(...),
    gate_id: str = Form(...),
):
    assign_slot(plate_number, slot_id, gate_id)
    print_receipt(plate_number, slot_id)
    return {"status": "printed", "slot_id": slot_id}


@app.post("/exit/detect")
async def exit_detect(gate_id: str = Form(...), image: UploadFile = File(...)):
    image_bytes = await image.read()
    plate_number = await run_in_threadpool(detect_plate, image_bytes)

    if not plate_number:
        return {"status": "no_plate_detected"}

    conn = get_connection()
    session = conn.execute(
        "SELECT * FROM parking_sessions WHERE plate_number = ? AND status = 'active'",
        (plate_number,),
    ).fetchone()

    if not session:
        conn.close()
        return {"status": "no_active_session", "plate_number": plate_number}

    conn.execute(
        "UPDATE slots SET status = 'free' WHERE slot_id = ?", (session["slot_id"],)
    )
    conn.execute(
        """UPDATE parking_sessions SET status = 'completed', exit_time = ?, gate_out = ?
           WHERE id = ?""",
        (datetime.now().isoformat(), gate_id, session["id"]),
    )
    conn.commit()
    conn.close()

    return {"status": "exited", "plate_number": plate_number, "slot_id": session["slot_id"]}


@app.get("/slots")
def get_slots():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM slots").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# Serve the gatekeeper frontend at http://localhost:8000/
app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")
