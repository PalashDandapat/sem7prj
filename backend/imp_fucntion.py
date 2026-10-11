from database import get_connection, init_db
from datetime import datetime

init_db()

def find_free_slot(gate_id: str):
    conn = get_connection()
    row = conn.execute(
        "SELECT slot_id FROM slots WHERE status = 'free' ORDER BY slot_id LIMIT 1"
    ).fetchone()
    conn.close()
    return row["slot_id"] if row else None


def try_claim_slot(plate_number: str, slot_id: str, gate_id: str) -> bool:
    """
    Atomically claim a slot. Returns False if someone else already took it
    (e.g. two gates scanning at the same moment).
    """
    conn = get_connection()
    cur = conn.execute(
        "UPDATE slots SET status = 'occupied' WHERE slot_id = ? AND status = 'free'",
        (slot_id,),
    )
    if cur.rowcount == 0:
        conn.close()
        return False

    conn.execute(
        """INSERT INTO parking_sessions (plate_number, slot_id, gate_in, entry_time, status)
           VALUES (?, ?, ?, ?, 'active')""",
        (plate_number, slot_id, gate_id, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    return True


def assign_slot(plate_number: str, preferred_slot: str | None, gate_id: str):
    """
    Try the preferred slot first; if it was taken meanwhile, fall back to the
    next free slot. Returns the slot actually assigned, or None if full.
    """
    if preferred_slot and try_claim_slot(plate_number, preferred_slot, gate_id):
        return preferred_slot

    for _ in range(5):  # a few retries in case of races
        slot_id = find_free_slot(gate_id)
        if not slot_id:
            return None
        if try_claim_slot(plate_number, slot_id, gate_id):
            return slot_id
    return None


def lookup_vehicle(plate_number: str):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM vehicles WHERE plate_number = ?", (plate_number,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def check_already_exist(plate_number: str):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM parking_sessions WHERE plate_number = ? AND status = 'active'",
        (plate_number,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None
