"""SQLite database layer for Premiumkreditkarte Worker."""

import sqlite3
from datetime import datetime, timedelta

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    customerId TEXT PRIMARY KEY,
    firstName TEXT NOT NULL,
    lastName TEXT NOT NULL,
    email TEXT,
    geburtsDatum DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS cards (
    cardId TEXT PRIMARY KEY,
    customerId TEXT NOT NULL REFERENCES customers(customerId),
    kartenNummer TEXT NOT NULL UNIQUE,
    activationStatus TEXT DEFAULT 'NICHT_AKTIVIERT',
    activationResult BOOLEAN,
    activationLocked BOOLEAN DEFAULT 0,
    lockedUntil TIMESTAMP,
    lockStatus TEXT,
    failedAttempts INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS activation_attempts (
    attemptId TEXT PRIMARY KEY,
    processInstanceKey TEXT,
    cardId TEXT REFERENCES cards(cardId),
    kartenNummer TEXT,
    geburtsDatum DATE,
    validationResult BOOLEAN,
    errorCode TEXT,
    failedAttempts INTEGER,
    createdAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pin_status (
    pinStatusId TEXT PRIMARY KEY,
    cardId TEXT REFERENCES cards(cardId),
    pinSet BOOLEAN DEFAULT 0,
    pinStatus TEXT DEFAULT 'NICHT_GESETZT',
    pinStorageResult TEXT,
    pinUpdatedAt TIMESTAMP
);

CREATE TABLE IF NOT EXISTS card_locks (
    lockId TEXT PRIMARY KEY,
    cardId TEXT REFERENCES cards(cardId),
    kartenNummer TEXT,
    activationLocked BOOLEAN DEFAULT 1,
    lockedUntil TIMESTAMP,
    lockReason TEXT,
    lockStatus TEXT DEFAULT 'AKTIVIERUNG_24H_GESPERRT',
    createdAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    releasedAt TIMESTAMP
);

CREATE TABLE IF NOT EXISTS mail_notifications (
    mailId TEXT PRIMARY KEY,
    customerId TEXT REFERENCES customers(customerId),
    cardId TEXT,
    mailType TEXT,
    mailRecipient TEXT,
    mailStatus TEXT,
    subject TEXT,
    sentAt TIMESTAMP,
    errorMessage TEXT
);

CREATE TABLE IF NOT EXISTS transactions (
    transactionId TEXT PRIMARY KEY,
    cardId TEXT REFERENCES cards(cardId),
    customerId TEXT REFERENCES customers(customerId),
    transactionAmount REAL,
    merchantName TEXT,
    mccCode TEXT,
    transactionDate DATE,
    transactionSaved BOOLEAN DEFAULT 0,
    mccRelevant BOOLEAN DEFAULT 0,
    transactionCategory TEXT,
    insuranceType TEXT,
    reisekaufErkannt BOOLEAN DEFAULT 0
);

CREATE TABLE IF NOT EXISTS mcc_rules (
    mccCode TEXT PRIMARY KEY,
    mccDescription TEXT,
    transactionCategory TEXT,
    insuranceType TEXT,
    isRelevant BOOLEAN
);

CREATE TABLE IF NOT EXISTS insurance (
    contractId TEXT PRIMARY KEY,
    cardId TEXT REFERENCES cards(cardId),
    customerId TEXT REFERENCES customers(customerId),
    transactionId TEXT REFERENCES transactions(transactionId),
    cvs TEXT,
    ablaufDatum DATE,
    offerStatus TEXT,
    offerMailSent BOOLEAN DEFAULT 0,
    offerMailRecipient TEXT,
    customerInterested BOOLEAN,
    offerDataValid BOOLEAN,
    offerValidationError TEXT,
    insuranceActivated BOOLEAN DEFAULT 0,
    insuranceStatus TEXT,
    trialStartDate DATE,
    trialEndDate DATE,
    insuranceMailSent BOOLEAN DEFAULT 0,
    insuranceMailType TEXT,
    insuranceMailRecipient TEXT,
    insuranceMailStatus TEXT
);
"""

SEED_DATA = """
INSERT OR IGNORE INTO customers VALUES ('C001','Max','Mustermann',NULL,'1990-03-15');
INSERT OR IGNORE INTO customers VALUES ('C002','Erika','Musterfrau',NULL,'1985-07-22');
INSERT OR IGNORE INTO customers VALUES ('C003','Tom','Beispiel',NULL,'2000-11-30');
INSERT OR IGNORE INTO customers VALUES ('C004','Lisa','Beispiel',NULL,'1999-01-01');
INSERT OR IGNORE INTO customers VALUES ('C005','Toni','Stange',NULL,'1978-12-05');
INSERT OR IGNORE INTO customers VALUES ('C006','Rocco','Sander',NULL,'2002-06-18');
INSERT OR IGNORE INTO customers VALUES ('C007','Tim','Diks',NULL,'1995-09-09');
INSERT OR IGNORE INTO customers VALUES ('C008','Jonas','Mohya',NULL,'1988-04-12');

INSERT OR IGNORE INTO cards VALUES ('CARD001','C001','1111222233334444','NICHT_AKTIVIERT',NULL,0,NULL,NULL,0);
INSERT OR IGNORE INTO cards VALUES ('CARD002','C002','5555666677778888','NICHT_AKTIVIERT',NULL,0,NULL,NULL,0);
INSERT OR IGNORE INTO cards VALUES ('CARD003','C003','9999000011112222','NICHT_AKTIVIERT',NULL,0,NULL,NULL,0);
INSERT OR IGNORE INTO cards VALUES ('CARD004','C004','1234567812345678','NICHT_AKTIVIERT',NULL,0,NULL,NULL,0);
INSERT OR IGNORE INTO cards VALUES ('CARD005','C005','4444333322221111','NICHT_AKTIVIERT',NULL,0,NULL,NULL,0);
INSERT OR IGNORE INTO cards VALUES ('CARD006','C006','8888777766665555','NICHT_AKTIVIERT',NULL,0,NULL,NULL,0);

INSERT OR IGNORE INTO mcc_rules VALUES ('7011','Hotels','TRAVEL','REISEVERSICHERUNG',1);
INSERT OR IGNORE INTO mcc_rules VALUES ('4722','Travel Agencies','TRAVEL','REISEVERSICHERUNG',1);
INSERT OR IGNORE INTO mcc_rules VALUES ('4511','Airlines','TRAVEL','REISEVERSICHERUNG',1);
INSERT OR IGNORE INTO mcc_rules VALUES ('5094','Precious Stones and Metals, Watches, and Jewellery','LUXURY','LUXUSGUETERVERSICHERUNG',1);
INSERT OR IGNORE INTO mcc_rules VALUES ('5944','Jewellery, Watch, Clock, and Silverware Stores','LUXURY','LUXUSGUETERVERSICHERUNG',1);
INSERT OR IGNORE INTO mcc_rules VALUES ('5999','Miscellaneous and Specialty Retail Shops','LUXURY','LUXUSGUETERVERSICHERUNG',1);
INSERT OR IGNORE INTO mcc_rules VALUES ('5411','Groceries stores & supermarkets','OTHER','NONE',0);
"""

_db_path = None


def init(db_path: str):
    """Initialize database: create tables and insert seed data."""
    global _db_path
    _db_path = db_path
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    conn.executescript(SEED_DATA)
    conn.commit()
    conn.close()


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# --- ID generators ---

def _next_id(prefix: str, table: str, id_col: str) -> str:
    conn = get_conn()
    row = conn.execute(f"SELECT COUNT(*) as cnt FROM {table}").fetchone()
    conn.close()
    return f"{prefix}{row['cnt'] + 1:03d}"


def next_attempt_id() -> str:
    return _next_id("A", "activation_attempts", "attemptId")


def next_pin_status_id() -> str:
    return _next_id("PIN", "pin_status", "pinStatusId")


def next_lock_id() -> str:
    return _next_id("LOCK", "card_locks", "lockId")


def next_mail_id() -> str:
    return _next_id("MAIL", "mail_notifications", "mailId")


def next_transaction_id() -> str:
    return _next_id("TR", "transactions", "transactionId")


def next_contract_id() -> str:
    return _next_id("CT", "insurance", "contractId")


# --- Query helpers ---

def get_card_by_number(kartenNummer: str) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM cards WHERE kartenNummer = ?", (kartenNummer,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_card(cardId: str) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM cards WHERE cardId = ?", (cardId,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_customer(customerId: str) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM customers WHERE customerId = ?", (customerId,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_mcc_rule(mccCode: str) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM mcc_rules WHERE mccCode = ?", (mccCode,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_insurance(contractId: str) -> dict | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM insurance WHERE contractId = ?", (contractId,)).fetchone()
    conn.close()
    return dict(row) if row else None


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def now_plus_24h() -> str:
    return (datetime.now() + timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
