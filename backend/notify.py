"""
Notification helpers: WhatsApp messaging and receipt printing.

WHATSAPP:
Real sending requires the WhatsApp Business API (e.g. via Twilio or Gupshup).
This stub just logs the message. To go live:
  1. Sign up for Twilio WhatsApp Sandbox (or Gupshup / Meta Cloud API).
  2. pip install twilio
  3. Fill in send_whatsapp() below with your account credentials.

PRINTING:
Real printing needs a local service on the gate PC talking to the receipt
printer (commonly via python-escpos for thermal printers). This stub just
logs what would be printed.
"""

def send_whatsapp(mobile_number: str, message: str) -> bool:
    """
    Send a WhatsApp message. Currently a stub — logs instead of sending.

    Example real implementation with Twilio:

        from twilio.rest import Client
        client = Client(ACCOUNT_SID, AUTH_TOKEN)
        client.messages.create(
            from_="whatsapp:+14155238886",   # Twilio sandbox number
            body=message,
            to=f"whatsapp:{mobile_number}",
        )
    """
    print(f"[WHATSAPP STUB] To: {mobile_number} | Message: {message}")
    return True


def print_receipt(plate_number: str, slot_id: str) -> bool:
    """
    Print a receipt. Currently a stub — logs instead of printing.

    Example real implementation with python-escpos (USB thermal printer):

        from escpos.printer import Usb
        p = Usb(0x04b8, 0x0202)  # vendor/product ID of your printer
        p.text(f"Plate: {plate_number}\nSlot: {slot_id}\n")
        p.cut()
    """
    print(f"[PRINT STUB] Receipt -> Plate: {plate_number} | Slot: {slot_id}")
    return True
