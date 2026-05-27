"""Camunda 8 Task Worker handlers for Fahrradwerkstatt (Gruppe 1)."""

import logging
import sqlite3

import db_bikes as db

logger = logging.getLogger("workers_bikes")


# ──────────────────────────────────────────────
# 1. bike-create-customer
# ──────────────────────────────────────────────

async def create_customer(
    name: str,
    strasse: str = None,
    plz: str = None,
    ort: str = None,
    email: str = None,
    **kwargs,
) -> dict:
    """Legt einen neuen Kunden an. E-Mail muss eindeutig sein."""
    conn = db.get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO kunden (name, strasse, plz, ort, email) VALUES (?, ?, ?, ?, ?)",
            (name, strasse, plz, ort, email),
        )
        kunden_id = cur.lastrowid
        conn.commit()
    except sqlite3.IntegrityError as e:
        conn.close()
        logger.warning("Kunde konnte nicht angelegt werden: %s", e)
        return {"created": False, "errorCode": "EMAIL_BEREITS_VORHANDEN", "kundenId": None}
    conn.close()
    logger.info("Kunde '%s' angelegt (kundenId=%s)", name, kunden_id)
    return {"created": True, "errorCode": None, "kundenId": kunden_id}


# ──────────────────────────────────────────────
# 2. bike-register-bike
# ──────────────────────────────────────────────

async def register_bike(kundenId: int, **kwargs) -> dict:
    """Registriert ein Fahrrad für einen bestehenden Kunden."""
    if not db.get_customer(kundenId):
        logger.warning("Fahrrad-Registrierung für unbekannten Kunden %s", kundenId)
        return {"registered": False, "errorCode": "KUNDE_UNBEKANNT", "objektId": None}

    conn = db.get_conn()
    cur = conn.execute("INSERT INTO fahrraeder (kundenId) VALUES (?)", (kundenId,))
    objekt_id = cur.lastrowid
    conn.commit()
    conn.close()
    logger.info("Fahrrad registriert (objektId=%s, kundenId=%s)", objekt_id, kundenId)
    return {"registered": True, "errorCode": None, "objektId": objekt_id}


# ──────────────────────────────────────────────
# 3. bike-create-order
# ──────────────────────────────────────────────

async def create_order(kundenId: int, objektId: int, **kwargs) -> dict:
    """Legt einen Auftrag mit Status 'offen' an."""
    bike = db.get_bike(objektId)
    if not bike:
        logger.warning("Auftragsanlage für unbekanntes Fahrrad %s", objektId)
        return {"created": False, "errorCode": "FAHRRAD_UNBEKANNT", "auftragsId": None, "status": None}
    if bike["kundenId"] != kundenId:
        logger.warning("Fahrrad %s gehört nicht zu Kunde %s", objektId, kundenId)
        return {"created": False, "errorCode": "FAHRRAD_GEHOERT_NICHT_KUNDE", "auftragsId": None, "status": None}

    conn = db.get_conn()
    cur = conn.execute(
        "INSERT INTO auftraege (kundenId, objektId, status) VALUES (?, ?, 'offen')",
        (kundenId, objektId),
    )
    auftrags_id = cur.lastrowid
    conn.commit()
    conn.close()
    logger.info("Auftrag %s angelegt (Kunde=%s, Fahrrad=%s)", auftrags_id, kundenId, objektId)
    return {"created": True, "errorCode": None, "auftragsId": auftrags_id, "status": "offen"}


# ──────────────────────────────────────────────
# 4. bike-update-order-status
# ──────────────────────────────────────────────

async def update_order_status(auftragsId: int, status: str, **kwargs) -> dict:
    """Setzt den Status eines Auftrags. Erlaubt: 'offen', 'in Bearbeitung', 'fertig'."""
    if status not in db.ALLOWED_STATUS:
        logger.warning("Ungültiger Status '%s' für Auftrag %s", status, auftragsId)
        return {"updated": False, "errorCode": "STATUS_UNGUELTIG", "auftragsId": auftragsId, "status": None}

    if not db.get_order(auftragsId):
        logger.warning("Statusupdate für unbekannten Auftrag %s", auftragsId)
        return {"updated": False, "errorCode": "AUFTRAG_UNBEKANNT", "auftragsId": auftragsId, "status": None}

    conn = db.get_conn()
    conn.execute("UPDATE auftraege SET status = ? WHERE auftragsId = ?", (status, auftragsId))
    conn.commit()
    conn.close()
    logger.info("Auftrag %s → Status '%s'", auftragsId, status)
    return {"updated": True, "errorCode": None, "auftragsId": auftragsId, "status": status}


# ──────────────────────────────────────────────
# 5. bike-get-customer
# ──────────────────────────────────────────────

async def get_customer(kundenId: int, **kwargs) -> dict:
    """Liest Kundendaten aus."""
    customer = db.get_customer(kundenId)
    if not customer:
        return {"found": False, "kundenId": kundenId}
    return {
        "found": True,
        "kundenId": customer["kundenId"],
        "name": customer["name"],
        "strasse": customer["strasse"],
        "plz": customer["plz"],
        "ort": customer["ort"],
        "email": customer["email"],
    }


# ──────────────────────────────────────────────
# 6. bike-get-order
# ──────────────────────────────────────────────

async def get_order(auftragsId: int, **kwargs) -> dict:
    """Liest Auftragsdaten aus."""
    order = db.get_order(auftragsId)
    if not order:
        return {"found": False, "auftragsId": auftragsId}
    return {
        "found": True,
        "auftragsId": order["auftragsId"],
        "kundenId": order["kundenId"],
        "objektId": order["objektId"],
        "status": order["status"],
    }
