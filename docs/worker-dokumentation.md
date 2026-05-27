# Premiumkreditkarte – Job Worker Dokumentation

## Überblick

Dieser Worker stellt **11 Service-Task-Handler** bereit, die über Camunda 8 SaaS angesprochen werden. Er verwaltet eine SQLite-Datenbank mit Kunden-, Karten-, Transaktions- und Versicherungsdaten.

> **Hinweis zur Schlüsselwahl:** `cardId` (z.B. `CARD001`) ist eine interne Datenbank-ID und sollte in BPMN-Prozessen **nicht** als Schlüssel verwendet werden. Für Transaktionsverarbeitung und Versicherungen stehen die Varianten `process-transaction-by-kartennummer` und `create-insurance-offer-by-kartennummer` zur Verfügung, die mit der fachlichen `kartenNummer` arbeiten. Die `-by-kartennummer`-Varianten sind für neue Prozesse zu bevorzugen.

Der Worker pollt automatisch bei Camunda nach offenen Jobs. Sobald ein BPMN-Prozess einen Service Task mit passendem **Task Type** erreicht, übernimmt der Worker die Verarbeitung.

---

## Architektur

```
┌──────────────────┐         HTTPS          ┌────────────────────┐
│  Camunda 8 SaaS  │◄──────────────────────►│  Python Worker     │
│  (BPMN-Prozess)  │    Job Poll / Complete  │                    │
└──────────────────┘                         │  ┌──────────────┐  │
                                             │  │  SQLite DB   │  │
                                             │  └──────────────┘  │
                                             └────────────────────┘
```

---

## Voraussetzungen

- Python 3.10+
- Camunda 8 SaaS Cluster mit API-Credentials (Client ID + Secret)
- Die Credentials erhaltet ihr vom Dozenten

---

## Setup

```bash
# Repository klonen
git clone <repo-url>
cd camunda-worker-cc

# Virtual Environment erstellen und aktivieren
python3 -m venv venv
source venv/bin/activate        # Linux/Mac
# venv\Scripts\activate         # Windows

# Abhängigkeiten installieren
pip install -r requirements.txt

# Konfiguration anlegen
cp .env.example .env
```

In der `.env`-Datei die Camunda-Credentials eintragen:

```env
CAMUNDA_CLIENT_ID=euer-client-id
CAMUNDA_CLIENT_SECRET=euer-client-secret
CAMUNDA_CLUSTER_ID=euer-cluster-id
CAMUNDA_REGION=bru-2
DB_PATH=premiumkreditkarte.db
```

### Worker starten

```bash
python main.py
```

Beim ersten Start wird die SQLite-Datenbank automatisch erstellt und mit Testdaten befüllt.

---

## Testdaten

### Kunden

| customerId | firstName | lastName    | geburtsDatum |
|------------|-----------|-------------|--------------|
| C001       | Max       | Mustermann  | 1990-03-15   |
| C002       | Erika     | Musterfrau  | 1985-07-22   |
| C003       | Tom       | Beispiel    | 2000-11-30   |
| C004       | Lisa      | Beispiel    | 1999-01-01   |
| C005       | Toni      | Stange      | 1978-12-05   |
| C006       | Rocco     | Sander      | 2002-06-18   |
| C007       | Tim       | Diks        | 1995-09-09   |
| C008       | Jonas     | Mohya       | 1988-04-12   |

### Karten

| cardId  | customerId | kartenNummer       |
|---------|------------|--------------------|
| CARD001 | C001       | 1111222233334444   |
| CARD002 | C002       | 5555666677778888   |
| CARD003 | C003       | 9999000011112222   |
| CARD004 | C004       | 1234567812345678   |
| CARD005 | C005       | 4444333322221111   |
| CARD006 | C006       | 8888777766665555   |

### MCC-Regeln

| mccCode | Beschreibung                  | Kategorie | Versicherungstyp          |
|---------|-------------------------------|-----------|---------------------------|
| 7011    | Hotels                        | TRAVEL    | REISEVERSICHERUNG         |
| 4722    | Travel Agencies               | TRAVEL    | REISEVERSICHERUNG         |
| 4511    | Airlines                      | TRAVEL    | REISEVERSICHERUNG         |
| 5094    | Precious Stones / Jewellery   | LUXURY    | LUXUSGUETERVERSICHERUNG   |
| 5944    | Jewellery / Watch Stores      | LUXURY    | LUXUSGUETERVERSICHERUNG   |
| 5999    | Specialty Retail Shops        | LUXURY    | LUXUSGUETERVERSICHERUNG   |
| 5411    | Groceries / Supermarkets      | OTHER     | NONE                      |

---

## Job Worker im BPMN-Prozess einbinden

### Prinzip

Jeder Service Task in eurem BPMN-Modell benötigt:

1. **Task Type** – identifiziert, welcher Worker-Handler den Job bearbeitet
2. **Input Mapping** – welche Prozessvariablen an den Worker übergeben werden
3. **Output Mapping** – welche Rückgabewerte in Prozessvariablen geschrieben werden

### Konfiguration im Camunda Modeler

Für jeden Service Task:

1. **Properties Panel** öffnen
2. **Implementation** → `Job worker` auswählen
3. **Task definition → Type** eintragen (z.B. `validate-card`)
4. **Input/Output** Mappings konfigurieren (siehe unten)

---

## Worker-Referenz

### 1. `validate-card`

Prüft Kartennummer und Geburtsdatum. Zählt Fehlversuche und sperrt nach 3 Fehlversuchen.

**Task Type:** `validate-card`

**Input-Variablen:**

| Variable       | Typ    | Beschreibung                        |
|----------------|--------|-------------------------------------|
| `kartenNummer` | String | 16-stellige Kartennummer            |
| `geburtsDatum` | String | Geburtsdatum im Format `YYYY-MM-DD` |

**Output-Variablen:**

| Variable           | Typ     | Beschreibung                          |
|--------------------|---------|---------------------------------------|
| `validationResult` | Boolean | `true` bei erfolgreicher Validierung  |
| `errorCode`        | String  | Fehlergrund (siehe unten) oder `null` |
| `failedAttempts`   | Integer | Aktuelle Anzahl Fehlversuche          |
| `cardId`           | String  | Karten-ID (z.B. `CARD001`)           |
| `customerId`       | String  | Kunden-ID (z.B. `C001`)              |

**Mögliche errorCodes:**

| errorCode              | Bedeutung                                   |
|------------------------|---------------------------------------------|
| `KARTE_UNBEKANNT`      | Kartennummer existiert nicht in der DB       |
| `GEBURTSDATUM_FALSCH`  | Geburtsdatum stimmt nicht überein            |
| `AKTIVIERUNG_GESPERRT` | Karte ist nach 3 Fehlversuchen 24h gesperrt |

**Beispiel Input Mapping:**

```
kartenNummer ← kartenNummer
geburtsDatum ← geburtsDatum
```

**Beispiel Output Mapping:**

```
validationResult → validationResult
errorCode        → errorCode
failedAttempts   → failedAttempts
cardId           → cardId
customerId       → customerId
```

---

### 2. `activate-card`

Setzt den Aktivierungsstatus einer validierten Karte auf `AKTIVIERT`.

**Task Type:** `activate-card`

**Input-Variablen:**

| Variable | Typ    | Beschreibung                     |
|----------|--------|----------------------------------|
| `cardId` | String | Karten-ID aus `validate-card`    |

**Output-Variablen:**

| Variable           | Typ    | Beschreibung    |
|--------------------|--------|-----------------|
| `activationStatus` | String | `AKTIVIERT`     |

---

### 3. `set-pin`

Speichert den PIN-Status (simuliert – es wird kein echter PIN gespeichert).

**Task Type:** `set-pin`

**Input-Variablen:**

| Variable | Typ    | Beschreibung                  |
|----------|--------|-------------------------------|
| `cardId` | String | Karten-ID                     |
| `pin`    | String | PIN (wird simuliert verarbeitet) |

**Output-Variablen:**

| Variable           | Typ     | Beschreibung                           |
|--------------------|---------|----------------------------------------|
| `pinSet`           | Boolean | `true`                                 |
| `pinStatus`        | String  | `GESETZT`                              |
| `pinStorageResult` | String  | `PIN_WURDE_SIMULIERT_GESPEICHERT`      |

---

### 4. `lock-card`

Sperrt die Kartenaktivierung für 24 Stunden (wird typischerweise nach 3 Fehlversuchen aufgerufen).

**Task Type:** `lock-card`

**Input-Variablen:**

| Variable | Typ    | Beschreibung |
|----------|--------|--------------|
| `cardId` | String | Karten-ID    |

**Output-Variablen:**

| Variable      | Typ    | Beschreibung                              |
|---------------|--------|-------------------------------------------|
| `lockStatus`  | String | `AKTIVIERUNG_24H_GESPERRT`                |
| `lockedUntil` | String | Zeitstempel bis wann gesperrt (`YYYY-MM-DD HH:mm:ss`) |

---

### 5. `check-lock-status`

Prüft, ob eine 24h-Sperre noch aktiv oder bereits abgelaufen ist.

**Task Type:** `check-lock-status`

**Input-Variablen:**

| Variable | Typ    | Beschreibung |
|----------|--------|--------------|
| `cardId` | String | Karten-ID    |

**Output-Variablen:**

| Variable           | Typ     | Beschreibung                                                |
|--------------------|---------|-------------------------------------------------------------|
| `activationLocked` | Boolean | `true` wenn Sperre noch aktiv                               |
| `lockStatus`       | String  | `AKTIVIERUNG_24H_GESPERRT`, `SPERRE_ABGELAUFEN` oder `KEINE_SPERRE` |

---

### 6. `send-mail`

Simuliert den Versand einer E-Mail und protokolliert ihn in der Datenbank.

**Task Type:** `send-mail`

**Input-Variablen:**

| Variable     | Typ    | Pflicht | Beschreibung           |
|--------------|--------|---------|------------------------|
| `customerId` | String | Ja      | Kunden-ID              |
| `mailType`   | String | Ja      | Art der Mail (frei wählbar, z.B. `AKTIVIERUNG`, `SPERRUNG`, `VERSICHERUNG`) |
| `subject`    | String | Ja      | Betreff                |
| `cardId`     | String | Nein    | Karten-ID (optional)   |

**Output-Variablen:**

| Variable     | Typ    | Beschreibung         |
|--------------|--------|----------------------|
| `mailStatus` | String | `VERSENDET_SANDBOX`  |
| `mailId`     | String | ID der Mail (z.B. `MAIL001`) |

> **Hinweis:** Es werden keine echten Mails versendet. Der Status ist immer `VERSENDET_SANDBOX`.

---

### 7. `process-transaction`

Speichert eine Kartentransaktion und prüft den MCC-Code gegen die Regeltabelle, um festzustellen, ob ein Versicherungsprozess ausgelöst werden soll.

**Task Type:** `process-transaction`

**Input-Variablen:**

| Variable            | Typ    | Beschreibung                       |
|---------------------|--------|------------------------------------|
| `cardId`            | String | Karten-ID                          |
| `transactionAmount` | Number | Betrag der Transaktion             |
| `merchantName`      | String | Name des Händlers                  |
| `mccCode`           | String | MCC-Code des Händlers (z.B. `7011`) |
| `transactionDate`   | String | Datum (`YYYY-MM-DD`)               |

**Output-Variablen:**

| Variable              | Typ     | Beschreibung                                    |
|-----------------------|---------|-------------------------------------------------|
| `transactionId`       | String  | ID der Transaktion (z.B. `TR001`)               |
| `mccRelevant`         | Boolean | `true` wenn MCC-Code versicherungsrelevant      |
| `transactionCategory` | String  | `TRAVEL`, `LUXURY` oder `OTHER`                 |
| `insuranceType`       | String  | `REISEVERSICHERUNG`, `LUXUSGUETERVERSICHERUNG` oder `NONE` |
| `reisekaufErkannt`    | Boolean | `true` bei Reise-Transaktionen                  |

**Fachliche Logik:**

Der Worker schlägt den `mccCode` in der MCC-Regeltabelle nach:
- **TRAVEL** (Hotels, Airlines, Reisebüros) → löst `REISEVERSICHERUNG` aus
- **LUXURY** (Schmuck, Uhren) → löst `LUXUSGUETERVERSICHERUNG` aus
- **OTHER** (Supermärkte etc.) → keine Versicherung

---

### 8. `create-insurance-offer`

Erstellt ein Versicherungsangebot basierend auf einer versicherungsrelevanten Transaktion.

**Task Type:** `create-insurance-offer`

**Input-Variablen:**

| Variable        | Typ    | Pflicht | Beschreibung                         |
|-----------------|--------|---------|--------------------------------------|
| `cardId`        | String | Ja      | Karten-ID                            |
| `transactionId` | String | Ja      | Transaktions-ID aus `process-transaction` |
| `insuranceType` | String | Ja      | Versicherungstyp aus `process-transaction` |
| `cvs`           | String | Nein    | Sicherheitscode der Karte            |
| `ablaufDatum`   | String | Nein    | Ablaufdatum der Karte (`YYYY-MM-DD`) |

**Output-Variablen:**

| Variable      | Typ    | Beschreibung                      |
|---------------|--------|-----------------------------------|
| `contractId`  | String | Vertrags-ID (z.B. `CT001`)       |
| `offerStatus` | String | `ANGEBOT_ERSTELLT`                |

---

### 7b. `process-transaction-by-kartennummer`

Identisch zu `process-transaction`, verwendet aber `kartenNummer` als fachlichen Schlüssel statt der internen `cardId`. **Empfohlen für neue BPMN-Prozesse.**

**Task Type:** `process-transaction-by-kartennummer`

**Input-Variablen:**

| Variable            | Typ    | Beschreibung                       |
|---------------------|--------|------------------------------------|
| `kartenNummer`      | String | 16-stellige Kartennummer           |
| `transactionAmount` | Number | Betrag der Transaktion             |
| `merchantName`      | String | Name des Händlers                  |
| `mccCode`           | String | MCC-Code des Händlers (z.B. `7011`) |
| `transactionDate`   | String | Datum (`YYYY-MM-DD`)               |

**Output-Variablen:**

| Variable              | Typ     | Beschreibung                                    |
|-----------------------|---------|-------------------------------------------------|
| `transactionId`       | String  | ID der Transaktion (z.B. `TR001`)               |
| `kartenNummer`        | String  | Kartennummer (für Folge-Tasks)                  |
| `mccRelevant`         | Boolean | `true` wenn MCC-Code versicherungsrelevant      |
| `transactionCategory` | String  | `TRAVEL`, `LUXURY` oder `OTHER`                 |
| `insuranceType`       | String  | `REISEVERSICHERUNG`, `LUXUSGUETERVERSICHERUNG` oder `NONE` |
| `reisekaufErkannt`    | Boolean | `true` bei Reise-Transaktionen                  |

> Ist die Kartennummer unbekannt, wird die Transaktion trotzdem gespeichert (mit `cardId = NULL`) und eine Warnung geloggt. Die Verarbeitung bricht nicht ab.

---

### 8b. `create-insurance-offer-by-kartennummer`

Identisch zu `create-insurance-offer`, verwendet aber `kartenNummer` als fachlichen Schlüssel. **Empfohlen für neue BPMN-Prozesse.**

**Task Type:** `create-insurance-offer-by-kartennummer`

**Input-Variablen:**

| Variable        | Typ    | Pflicht | Beschreibung                              |
|-----------------|--------|---------|-------------------------------------------|
| `kartenNummer`  | String | Ja      | Kartennummer                              |
| `transactionId` | String | Ja      | Transaktions-ID aus `process-transaction-by-kartennummer` |
| `insuranceType` | String | Ja      | Versicherungstyp aus `process-transaction-by-kartennummer` |
| `cvs`           | String | Nein    | Sicherheitscode der Karte                 |
| `ablaufDatum`   | String | Nein    | Ablaufdatum der Karte (`YYYY-MM-DD`)      |

**Output-Variablen:**

| Variable       | Typ    | Beschreibung                      |
|----------------|--------|-----------------------------------|
| `contractId`   | String | Vertrags-ID (z.B. `CT001`)       |
| `kartenNummer` | String | Kartennummer (für Folge-Tasks)    |
| `offerStatus`  | String | `ANGEBOT_ERSTELLT`                |

---

### 9. `activate-insurance`

Aktiviert eine Versicherung mit einer kostenlosen 30-Tage-Testphase.

**Task Type:** `activate-insurance`

**Input-Variablen:**

| Variable     | Typ    | Beschreibung                           |
|--------------|--------|----------------------------------------|
| `contractId` | String | Vertrags-ID aus `create-insurance-offer` |

**Output-Variablen:**

| Variable             | Typ     | Beschreibung                   |
|----------------------|---------|---------------------------------|
| `insuranceActivated` | Boolean | `true`                         |
| `insuranceStatus`    | String  | `AKTIV`                        |
| `trialStartDate`     | String  | Beginn Testphase (`YYYY-MM-DD`) |
| `trialEndDate`       | String  | Ende Testphase (`YYYY-MM-DD`)   |

---

## Typische Prozessabläufe

### Kartenaktivierung

```
Start → validate-card → [Erfolg?]
                           ├─ Ja → activate-card → set-pin → send-mail → Ende
                           └─ Nein → [3 Fehlversuche?]
                                        ├─ Ja → lock-card → send-mail → Ende
                                        └─ Nein → Erneuter Versuch
```

### Transaktionsverarbeitung mit Versicherung (empfohlen – mit Kartennummer)

```
Start → process-transaction-by-kartennummer → [mccRelevant?]
                                                  ├─ Ja → create-insurance-offer-by-kartennummer → [Kunde interessiert?]
                                                  │                                                   ├─ Ja → activate-insurance → send-mail → Ende
                                                  │                                                   └─ Nein → Ende
                                                  └─ Nein → Ende
```

### Transaktionsverarbeitung mit Versicherung (Legacy – mit cardId)

```
Start → process-transaction → [mccRelevant?]
                                  ├─ Ja → create-insurance-offer → [Kunde interessiert?]
                                  │                                    ├─ Ja → activate-insurance → send-mail → Ende
                                  │                                    └─ Nein → Ende
                                  └─ Nein → Ende
```

---

## Tipps zur Fehlersuche

- **Worker-Logs prüfen:** Der Worker gibt alle Aktionen auf der Konsole aus
- **Datenbank inspizieren:** Mit einem SQLite-Browser (z.B. DB Browser for SQLite) die Datei `premiumkreditkarte.db` öffnen
- **Datenbank zurücksetzen:** Einfach `premiumkreditkarte.db` löschen und den Worker neu starten
- **Variable nicht angekommen?** Prüft das Input Mapping im Camunda Modeler – der Variablenname muss exakt übereinstimmen (case-sensitive)
