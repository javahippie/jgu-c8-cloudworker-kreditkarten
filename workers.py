"""Camunda 8 Task Worker handlers for Premiumkreditkarte."""

import logging
from datetime import datetime, timedelta

import db

logger = logging.getLogger("workers")


# ──────────────────────────────────────────────
# 1. validate-card
# ──────────────────────────────────────────────

async def validate_card(kartenNummer: str, geburtsDatum: str, **kwargs) -> dict:
    """
    Prüft Kartennummer + Geburtsdatum gegen die Datenbank.
    Zählt Fehlversuche hoch und sperrt nach 3 Fehlversuchen.
    """
    card = db.get_card_by_number(kartenNummer)

    if not card:
        attempt_id = db.next_attempt_id()
        conn = db.get_conn()
        conn.execute(
            "INSERT INTO activation_attempts (attemptId, cardId, kartenNummer, geburtsDatum, validationResult, errorCode, failedAttempts, createdAt) "
            "VALUES (?, NULL, ?, ?, 0, 'KARTE_UNBEKANNT', 0, ?)",
            (attempt_id, kartenNummer, geburtsDatum, db.now()),
        )
        conn.commit()
        conn.close()
        return {
            "validationResult": False,
            "errorCode": "KARTE_UNBEKANNT",
            "failedAttempts": 0,
            "cardId": None,
            "customerId": None,
        }

    card_id = card["cardId"]
    customer_id = card["customerId"]

    # Prüfe ob Aktivierung gesperrt
    if card["activationLocked"]:
        locked_until = card.get("lockedUntil")
        if locked_until and datetime.strptime(locked_until, "%Y-%m-%d %H:%M:%S") > datetime.now():
            return {
                "validationResult": False,
                "errorCode": "AKTIVIERUNG_GESPERRT",
                "failedAttempts": card["failedAttempts"],
                "cardId": card_id,
                "customerId": customer_id,
            }
        else:
            # Sperre abgelaufen → entsperren
            conn = db.get_conn()
            conn.execute(
                "UPDATE cards SET activationLocked = 0, lockStatus = 'SPERRE_ABGELAUFEN', failedAttempts = 0 WHERE cardId = ?",
                (card_id,),
            )
            conn.execute(
                "UPDATE card_locks SET lockStatus = 'SPERRE_ABGELAUFEN', releasedAt = ? WHERE cardId = ? AND lockStatus = 'AKTIVIERUNG_24H_GESPERRT'",
                (db.now(), card_id),
            )
            conn.commit()
            conn.close()
            card["failedAttempts"] = 0

    # Geburtsdatum prüfen
    customer = db.get_customer(customer_id)
    input_date = geburtsDatum[:10]  # normalisiere auf YYYY-MM-DD
    stored_date = customer["geburtsDatum"][:10]

    if input_date != stored_date:
        new_attempts = card["failedAttempts"] + 1
        error_code = "GEBURTSDATUM_FALSCH"

        conn = db.get_conn()
        conn.execute(
            "UPDATE cards SET failedAttempts = ? WHERE cardId = ?",
            (new_attempts, card_id),
        )

        # Nach 3 Fehlversuchen sperren
        if new_attempts >= 3:
            locked_until = db.now_plus_24h()
            conn.execute(
                "UPDATE cards SET activationLocked = 1, lockedUntil = ?, lockStatus = 'AKTIVIERUNG_24H_GESPERRT' WHERE cardId = ?",
                (locked_until, card_id),
            )
            lock_id = db.next_lock_id()
            conn.execute(
                "INSERT INTO card_locks (lockId, cardId, kartenNummer, activationLocked, lockedUntil, lockReason, lockStatus, createdAt) "
                "VALUES (?, ?, ?, 1, ?, 'ZU_VIELE_FEHLVERSUCHE', 'AKTIVIERUNG_24H_GESPERRT', ?)",
                (lock_id, card_id, kartenNummer, locked_until, db.now()),
            )
            error_code = "AKTIVIERUNG_GESPERRT"

        attempt_id = db.next_attempt_id()
        conn.execute(
            "INSERT INTO activation_attempts (attemptId, cardId, kartenNummer, geburtsDatum, validationResult, errorCode, failedAttempts, createdAt) "
            "VALUES (?, ?, ?, ?, 0, ?, ?, ?)",
            (attempt_id, card_id, kartenNummer, geburtsDatum, error_code, new_attempts, db.now()),
        )
        conn.commit()
        conn.close()

        return {
            "validationResult": False,
            "errorCode": error_code,
            "failedAttempts": new_attempts,
            "cardId": card_id,
            "customerId": customer_id,
        }

    # Erfolg
    conn = db.get_conn()
    conn.execute("UPDATE cards SET failedAttempts = 0 WHERE cardId = ?", (card_id,))
    attempt_id = db.next_attempt_id()
    conn.execute(
        "INSERT INTO activation_attempts (attemptId, cardId, kartenNummer, geburtsDatum, validationResult, errorCode, failedAttempts, createdAt) "
        "VALUES (?, ?, ?, ?, 1, NULL, 0, ?)",
        (attempt_id, card_id, kartenNummer, geburtsDatum, db.now()),
    )
    conn.commit()
    conn.close()

    return {
        "validationResult": True,
        "errorCode": None,
        "failedAttempts": 0,
        "cardId": card_id,
        "customerId": customer_id,
    }


# ──────────────────────────────────────────────
# 2. activate-card
# ──────────────────────────────────────────────

async def activate_card(cardId: str, **kwargs) -> dict:
    """Setzt den Aktivierungsstatus der Karte auf AKTIVIERT."""
    conn = db.get_conn()
    conn.execute(
        "UPDATE cards SET activationStatus = 'AKTIVIERT', activationResult = 1 WHERE cardId = ?",
        (cardId,),
    )
    conn.commit()
    conn.close()
    logger.info("Karte %s aktiviert", cardId)
    return {"activationStatus": "AKTIVIERT"}


# ──────────────────────────────────────────────
# 3. set-pin
# ──────────────────────────────────────────────

async def set_pin(cardId: str, pin: str, **kwargs) -> dict:
    """Speichert den PIN-Status (simuliert)."""
    pin_status_id = db.next_pin_status_id()
    conn = db.get_conn()
    conn.execute(
        "INSERT INTO pin_status (pinStatusId, cardId, pinSet, pinStatus, pinStorageResult, pinUpdatedAt) "
        "VALUES (?, ?, 1, 'GESETZT', 'PIN_WURDE_SIMULIERT_GESPEICHERT', ?)",
        (pin_status_id, cardId, db.now()),
    )
    conn.commit()
    conn.close()
    logger.info("PIN für Karte %s gesetzt (simuliert)", cardId)
    return {
        "pinSet": True,
        "pinStatus": "GESETZT",
        "pinStorageResult": "PIN_WURDE_SIMULIERT_GESPEICHERT",
    }


# ──────────────────────────────────────────────
# 4. lock-card
# ──────────────────────────────────────────────

async def lock_card(cardId: str, **kwargs) -> dict:
    """Sperrt die Kartenaktivierung für 24 Stunden."""
    locked_until = db.now_plus_24h()
    lock_id = db.next_lock_id()
    card = db.get_card(cardId)
    kartenNummer = card["kartenNummer"] if card else None

    conn = db.get_conn()
    conn.execute(
        "UPDATE cards SET activationLocked = 1, lockedUntil = ?, lockStatus = 'AKTIVIERUNG_24H_GESPERRT' WHERE cardId = ?",
        (locked_until, cardId),
    )
    conn.execute(
        "INSERT INTO card_locks (lockId, cardId, kartenNummer, activationLocked, lockedUntil, lockReason, lockStatus, createdAt) "
        "VALUES (?, ?, ?, 1, ?, 'ZU_VIELE_FEHLVERSUCHE', 'AKTIVIERUNG_24H_GESPERRT', ?)",
        (lock_id, cardId, kartenNummer, locked_until, db.now()),
    )
    conn.commit()
    conn.close()
    logger.info("Karte %s gesperrt bis %s", cardId, locked_until)
    return {"lockStatus": "AKTIVIERUNG_24H_GESPERRT", "lockedUntil": locked_until}


# ──────────────────────────────────────────────
# 5. check-lock-status
# ──────────────────────────────────────────────

async def check_lock_status(cardId: str, **kwargs) -> dict:
    """Prüft ob die 24h-Sperre noch aktiv ist."""
    card = db.get_card(cardId)
    if not card or not card["activationLocked"]:
        return {"activationLocked": False, "lockStatus": "KEINE_SPERRE"}

    locked_until = card.get("lockedUntil")
    if locked_until and datetime.strptime(locked_until, "%Y-%m-%d %H:%M:%S") <= datetime.now():
        conn = db.get_conn()
        conn.execute(
            "UPDATE cards SET activationLocked = 0, lockStatus = 'SPERRE_ABGELAUFEN', failedAttempts = 0 WHERE cardId = ?",
            (cardId,),
        )
        conn.execute(
            "UPDATE card_locks SET lockStatus = 'SPERRE_ABGELAUFEN', releasedAt = ? WHERE cardId = ? AND lockStatus = 'AKTIVIERUNG_24H_GESPERRT'",
            (db.now(), cardId),
        )
        conn.commit()
        conn.close()
        return {"activationLocked": False, "lockStatus": "SPERRE_ABGELAUFEN"}

    return {"activationLocked": True, "lockStatus": "AKTIVIERUNG_24H_GESPERRT"}


# ──────────────────────────────────────────────
# 6. send-mail
# ──────────────────────────────────────────────

async def send_mail(customerId: str, mailType: str, subject: str, cardId: str = None, **kwargs) -> dict:
    """Simuliert den Mailversand und protokolliert ihn."""
    customer = db.get_customer(customerId)
    recipient = customer["email"] if customer and customer["email"] else f"{customerId}@sandbox.local"

    mail_id = db.next_mail_id()
    conn = db.get_conn()
    conn.execute(
        "INSERT INTO mail_notifications (mailId, customerId, cardId, mailType, mailRecipient, mailStatus, subject, sentAt, errorMessage) "
        "VALUES (?, ?, ?, ?, ?, 'VERSENDET_SANDBOX', ?, ?, NULL)",
        (mail_id, customerId, cardId, mailType, recipient, subject, db.now()),
    )
    conn.commit()
    conn.close()
    logger.info("Mail '%s' an %s gesendet (Sandbox)", subject, recipient)
    return {"mailStatus": "VERSENDET_SANDBOX", "mailId": mail_id}


# ──────────────────────────────────────────────
# 7. process-transaction
# ──────────────────────────────────────────────

async def process_transaction(
    cardId: str,
    transactionAmount: float,
    merchantName: str,
    mccCode: str,
    transactionDate: str,
    **kwargs,
) -> dict:
    """Verarbeitet eine Transaktion und prüft MCC-Regeln."""
    card = db.get_card(cardId)
    customer_id = card["customerId"] if card else None

    rule = db.get_mcc_rule(mccCode)
    if rule:
        mcc_relevant = bool(rule["isRelevant"])
        transaction_category = rule["transactionCategory"]
        insurance_type = rule["insuranceType"]
    else:
        mcc_relevant = False
        transaction_category = "OTHER"
        insurance_type = "NONE"

    reisekauf_erkannt = transaction_category == "TRAVEL"

    transaction_id = db.next_transaction_id()
    conn = db.get_conn()
    conn.execute(
        "INSERT INTO transactions (transactionId, cardId, customerId, transactionAmount, merchantName, mccCode, transactionDate, transactionSaved, mccRelevant, transactionCategory, insuranceType, reisekaufErkannt) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)",
        (
            transaction_id, cardId, customer_id, transactionAmount,
            merchantName, mccCode, transactionDate, int(mcc_relevant),
            transaction_category, insurance_type, int(reisekauf_erkannt),
        ),
    )
    conn.commit()
    conn.close()
    logger.info("Transaktion %s gespeichert (MCC %s → %s)", transaction_id, mccCode, transaction_category)
    return {
        "transactionId": transaction_id,
        "mccRelevant": mcc_relevant,
        "transactionCategory": transaction_category,
        "insuranceType": insurance_type,
        "reisekaufErkannt": reisekauf_erkannt,
    }


# ──────────────────────────────────────────────
# 8. create-insurance-offer
# ──────────────────────────────────────────────

async def create_insurance_offer(
    cardId: str,
    transactionId: str,
    insuranceType: str,
    cvs: str = None,
    ablaufDatum: str = None,
    **kwargs,
) -> dict:
    """Erstellt ein Versicherungsangebot."""
    card = db.get_card(cardId)
    customer_id = card["customerId"] if card else None

    contract_id = db.next_contract_id()
    conn = db.get_conn()
    conn.execute(
        "INSERT INTO insurance (contractId, cardId, customerId, transactionId, cvs, ablaufDatum, offerStatus, insuranceStatus) "
        "VALUES (?, ?, ?, ?, ?, ?, 'ANGEBOT_ERSTELLT', 'OFFEN')",
        (contract_id, cardId, customer_id, transactionId, cvs, ablaufDatum),
    )
    conn.commit()
    conn.close()
    logger.info("Versicherungsangebot %s erstellt (%s)", contract_id, insuranceType)
    return {"contractId": contract_id, "offerStatus": "ANGEBOT_ERSTELLT"}


# ──────────────────────────────────────────────
# 9. activate-insurance
# ──────────────────────────────────────────────

async def activate_insurance(contractId: str, **kwargs) -> dict:
    """Aktiviert eine Versicherung mit kostenloser Testphase (30 Tage)."""
    trial_start = datetime.now().strftime("%Y-%m-%d")
    trial_end = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

    conn = db.get_conn()
    conn.execute(
        "UPDATE insurance SET insuranceActivated = 1, insuranceStatus = 'AKTIV', "
        "trialStartDate = ?, trialEndDate = ?, offerStatus = 'ANGENOMMEN' "
        "WHERE contractId = ?",
        (trial_start, trial_end, contractId),
    )
    conn.commit()
    conn.close()
    logger.info("Versicherung %s aktiviert (Testphase bis %s)", contractId, trial_end)
    return {
        "insuranceActivated": True,
        "insuranceStatus": "AKTIV",
        "trialStartDate": trial_start,
        "trialEndDate": trial_end,
    }
