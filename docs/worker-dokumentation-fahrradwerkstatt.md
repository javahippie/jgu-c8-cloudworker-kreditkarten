# Fahrradwerkstatt – Job Worker Dokumentation (Gruppe 1)

## Überblick

Dieser Worker stellt **6 Service-Task-Handler** für die Fahrradwerkstatt bereit, die über Camunda 8 SaaS angesprochen werden. Er verwaltet eine eigene SQLite-Datenbank (`fahrradwerkstatt.db`) mit Kunden-, Fahrrad- und Auftragsdaten.

Der Worker pollt automatisch bei Camunda nach offenen Jobs. Sobald ein BPMN-Prozess einen Service Task mit passendem **Task Type** erreicht, übernimmt der Worker die Verarbeitung.

> **Hinweis:** Alle Task Types der Fahrradwerkstatt sind mit dem Präfix `bike-` versehen, damit sie sich nicht mit Tasks anderer Gruppen überschneiden. Eure BPMN-Prozesse müssen genau diese Präfixe verwenden.

---

## Architektur

```
┌──────────────────┐         HTTPS          ┌────────────────────┐
│  Camunda 8 SaaS  │◄──────────────────────►│  Python Worker     │
│  (BPMN-Prozess)  │   Job Poll / Complete  │                    │
└──────────────────┘                        │  ┌──────────────┐  │
                                            │  │ fahrrad-     │  │
                                            │  │ werkstatt.db │  │
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
BIKE_DB_PATH=fahrradwerkstatt.db
```

### Worker starten

```bash
python main.py
```

Beim ersten Start wird die SQLite-Datenbank `fahrradwerkstatt.db` automatisch erstellt – sie ist beim ersten Start leer. Kunden, Fahrräder und Aufträge werden über die BPMN-Tasks (`bike-create-customer`, `bike-register-bike`, `bike-create-order`) angelegt.

---

## Datenbankschema

### Tabelle `kunden`

| Spalte       | Typ           | Constraint                                |
|--------------|---------------|-------------------------------------------|
| `kundenId`   | INTEGER       | PRIMARY KEY, AUTOINCREMENT                |
| `name`       | TEXT          | NOT NULL                                  |
| `strasse`    | TEXT          |                                           |
| `plz`        | TEXT          |                                           |
| `ort`        | TEXT          |                                           |
| `email`      | TEXT          | UNIQUE                                    |

### Tabelle `fahrraeder`

| Spalte      | Typ     | Constraint                                  |
|-------------|---------|---------------------------------------------|
| `objektId`  | INTEGER | PRIMARY KEY, AUTOINCREMENT                  |
| `kundenId`  | INTEGER | NOT NULL, FK → `kunden(kundenId)`           |

### Tabelle `auftraege`

| Spalte       | Typ     | Constraint                                                                       |
|--------------|---------|----------------------------------------------------------------------------------|
| `auftragsId` | INTEGER | PRIMARY KEY, AUTOINCREMENT                                                       |
| `kundenId`   | INTEGER | NOT NULL, FK → `kunden(kundenId)`                                                |
| `objektId`   | INTEGER | NOT NULL, FK → `fahrraeder(objektId)`                                            |
| `status`     | TEXT    | NOT NULL, DEFAULT `'offen'`, CHECK `IN ('offen', 'in Bearbeitung', 'fertig')`    |

> IDs werden automatisch von SQLite vergeben (Auto-Increment). Die Worker geben die neu vergebene ID jeweils im Output zurück, damit ihr sie im BPMN-Prozess in Folge-Tasks weiterverwenden könnt.

---

## Job Worker im BPMN-Prozess einbinden

### Prinzip

Jeder Service Task in eurem BPMN-Modell benötigt:

1. **Task Type** – identifiziert, welcher Worker-Handler den Job bearbeitet (z.B. `bike-create-customer`)
2. **Input Mapping** – welche Prozessvariablen an den Worker übergeben werden
3. **Output Mapping** – welche Rückgabewerte in Prozessvariablen geschrieben werden

### Konfiguration im Camunda Modeler

Für jeden Service Task:

1. **Properties Panel** öffnen
2. **Implementation** → `Job worker` auswählen
3. **Task definition → Type** eintragen (z.B. `bike-create-customer`)
4. **Input/Output** Mappings konfigurieren (siehe unten)

---

## Worker-Referenz

### 1. `bike-create-customer`

Legt einen neuen Kunden an. Die E-Mail-Adresse muss eindeutig sein – existiert sie bereits, wird der Kunde **nicht** angelegt und ein Fehlercode zurückgegeben.

**Task Type:** `bike-create-customer`

**Input-Variablen:**

| Variable   | Typ    | Pflicht | Beschreibung                          |
|------------|--------|---------|---------------------------------------|
| `name`     | String | Ja      | Name des Kunden (max. 100 Zeichen)    |
| `strasse`  | String | Nein    | Straße + Hausnummer                   |
| `plz`      | String | Nein    | Postleitzahl                          |
| `ort`      | String | Nein    | Ort                                   |
| `email`    | String | Nein    | E-Mail-Adresse (muss eindeutig sein)  |

**Output-Variablen:**

| Variable    | Typ     | Beschreibung                                          |
|-------------|---------|-------------------------------------------------------|
| `created`   | Boolean | `true` bei erfolgreicher Anlage, sonst `false`        |
| `errorCode` | String  | `null` oder `EMAIL_BEREITS_VORHANDEN`                 |
| `kundenId`  | Integer | Neu vergebene Kunden-ID oder `null` im Fehlerfall     |

---

### 2. `bike-register-bike`

Registriert ein Fahrrad für einen bestehenden Kunden.

**Task Type:** `bike-register-bike`

**Input-Variablen:**

| Variable    | Typ     | Pflicht | Beschreibung                |
|-------------|---------|---------|-----------------------------|
| `kundenId`  | Integer | Ja      | ID des Besitzers            |

**Output-Variablen:**

| Variable     | Typ     | Beschreibung                                       |
|--------------|---------|----------------------------------------------------|
| `registered` | Boolean | `true` bei erfolgreicher Registrierung             |
| `errorCode`  | String  | `null` oder `KUNDE_UNBEKANNT`                      |
| `objektId`   | Integer | Neu vergebene Fahrrad-ID oder `null` im Fehlerfall |

---

### 3. `bike-create-order`

Legt einen neuen Reparaturauftrag mit Status `offen` an. Validiert, dass das Fahrrad zum angegebenen Kunden gehört.

**Task Type:** `bike-create-order`

**Input-Variablen:**

| Variable   | Typ     | Pflicht | Beschreibung           |
|------------|---------|---------|------------------------|
| `kundenId` | Integer | Ja      | ID des Kunden          |
| `objektId` | Integer | Ja      | ID des Fahrrads        |

**Output-Variablen:**

| Variable     | Typ     | Beschreibung                                                              |
|--------------|---------|---------------------------------------------------------------------------|
| `created`    | Boolean | `true` bei erfolgreicher Anlage                                           |
| `errorCode`  | String  | `null`, `FAHRRAD_UNBEKANNT` oder `FAHRRAD_GEHOERT_NICHT_KUNDE`            |
| `auftragsId` | Integer | Neu vergebene Auftrags-ID oder `null` im Fehlerfall                       |
| `status`     | String  | `'offen'` bei Erfolg, sonst `null`                                        |

---

### 4. `bike-update-order-status`

Setzt den Status eines bestehenden Auftrags. Nur die drei vordefinierten Werte sind erlaubt: `offen`, `in Bearbeitung`, `fertig` (Achtung: case-sensitive und Leerzeichen exakt!).

**Task Type:** `bike-update-order-status`

**Input-Variablen:**

| Variable     | Typ     | Pflicht | Beschreibung                                              |
|--------------|---------|---------|-----------------------------------------------------------|
| `auftragsId` | Integer | Ja      | ID des Auftrags                                           |
| `status`     | String  | Ja      | Neuer Status: `offen`, `in Bearbeitung` oder `fertig`     |

**Output-Variablen:**

| Variable     | Typ     | Beschreibung                                              |
|--------------|---------|-----------------------------------------------------------|
| `updated`    | Boolean | `true` bei erfolgreichem Update                           |
| `errorCode`  | String  | `null`, `STATUS_UNGUELTIG` oder `AUFTRAG_UNBEKANNT`       |
| `auftragsId` | Integer | Auftrags-ID (Echo)                                        |
| `status`     | String  | Neuer Status bei Erfolg, sonst `null`                     |

---

### 5. `bike-get-customer`

Liest die Daten eines Kunden aus der Datenbank.

**Task Type:** `bike-get-customer`

**Input-Variablen:**

| Variable   | Typ     | Pflicht | Beschreibung   |
|------------|---------|---------|----------------|
| `kundenId` | Integer | Ja      | ID des Kunden  |

**Output-Variablen:**

| Variable    | Typ     | Beschreibung                                       |
|-------------|---------|----------------------------------------------------|
| `found`     | Boolean | `true` wenn Kunde existiert                        |
| `kundenId`  | Integer | Kunden-ID                                          |
| `name`      | String  | Name (nur bei `found=true`)                        |
| `strasse`   | String  | Straße (nur bei `found=true`, ggf. `null`)         |
| `plz`       | String  | PLZ (nur bei `found=true`, ggf. `null`)            |
| `ort`       | String  | Ort (nur bei `found=true`, ggf. `null`)            |
| `email`     | String  | E-Mail (nur bei `found=true`, ggf. `null`)         |

---

### 6. `bike-get-order`

Liest die Daten eines Auftrags aus der Datenbank.

**Task Type:** `bike-get-order`

**Input-Variablen:**

| Variable     | Typ     | Pflicht | Beschreibung     |
|--------------|---------|---------|------------------|
| `auftragsId` | Integer | Ja      | ID des Auftrags  |

**Output-Variablen:**

| Variable     | Typ     | Beschreibung                                                                |
|--------------|---------|-----------------------------------------------------------------------------|
| `found`      | Boolean | `true` wenn Auftrag existiert                                               |
| `auftragsId` | Integer | Auftrags-ID                                                                 |
| `kundenId`   | Integer | Kunden-ID (nur bei `found=true`)                                            |
| `objektId`   | Integer | Fahrrad-ID (nur bei `found=true`)                                           |
| `status`     | String  | `offen`, `in Bearbeitung` oder `fertig` (nur bei `found=true`)              |

---

## Typischer Prozessablauf

### Neukunde mit erstem Reparaturauftrag

```
Start → bike-create-customer → [created?]
                                  ├─ Ja → bike-register-bike → bike-create-order
                                  │                                  │
                                  │                                  ▼
                                  │                          bike-update-order-status
                                  │                          (status='in Bearbeitung')
                                  │                                  │
                                  │                                  ▼
                                  │                          bike-update-order-status
                                  │                          (status='fertig')
                                  │                                  │
                                  │                                  ▼
                                  │                                Ende
                                  └─ Nein → [errorCode prüfen] → Ende
```

### Folgeauftrag eines bestehenden Kunden

```
Start → bike-get-customer → [found?]
                              ├─ Ja → bike-register-bike → bike-create-order → ...
                              └─ Nein → Ende (Kunde existiert nicht)
```

---

## Tipps zur Fehlersuche

- **Worker-Logs prüfen:** Der Worker gibt alle Aktionen auf der Konsole aus (z.B. `Kunde 'Max' angelegt (kundenId=1)`)
- **Datenbank inspizieren:** Mit einem SQLite-Browser (z.B. DB Browser for SQLite) die Datei `fahrradwerkstatt.db` öffnen
- **Datenbank zurücksetzen:** Die Datei `fahrradwerkstatt.db` löschen und den Worker neu starten – die Tabellen werden automatisch neu angelegt. Die DB der anderen Gruppen wird dadurch **nicht** berührt.
- **Variable nicht angekommen?** Prüft das Input Mapping im Camunda Modeler – der Variablenname muss exakt übereinstimmen (case-sensitive). Beispiel: `kundenId`, nicht `KundenID` oder `kundenid`.
- **`errorCode` immer prüfen:** Alle Schreiboperationen geben bei Fehlern einen `errorCode` zurück statt eine Exception zu werfen. Eure BPMN-Prozesse sollten den Wert auswerten und entsprechende Gateways/Boundary-Events vorsehen.
- **Status exakt schreiben:** `'in Bearbeitung'` mit Leerzeichen und Großschreibung. Abweichungen werden mit `STATUS_UNGUELTIG` abgelehnt.
