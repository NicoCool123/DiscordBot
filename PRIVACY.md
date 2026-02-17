# 🔒 Datenschutz & Minimale Datenspeicherung

## Übersicht

Dieser Discord Bot ist so konfiguriert, dass **nur die absolut notwendigsten Daten** gespeichert werden.

---

## ✅ Was wird NICHT gespeichert (mit minimaler Konfiguration)

- ❌ **Keine Audit Logs** (Aktivitätsprotokolle komplett deaktiviert)
- ❌ **Keine IP-Adressen**
- ❌ **Keine User-Agents** (Browser-Informationen)
- ❌ **Keine API-Nutzungsstatistiken** (last_used_at, usage_count entfernt)
- ❌ **Keine Nachrichteninhalte**
- ❌ **Keine Discord-Nachrichten**

---

## 📊 Was wird MINIMAL gespeichert

### 1. **Benutzerkonten** (ERFORDERLICH für Authentifizierung)

| Feld | Zweck | Löschbar? |
|------|-------|-----------|
| `username` | Login-Name | ✅ Ja (Account löschen) |
| `email` | Wiederherstellung, Kommunikation | ✅ Ja |
| `password_hash` | Sicheres Login (NIEMALS Klartext!) | ✅ Ja |
| `discord_id` | Discord OAuth Login | ✅ Ja |
| `created_at` | Account-Erstellung | ✅ Ja |

**Warum erforderlich?**
Ohne diese Daten kannst du dich nicht einloggen und den Bot nicht verwalten.

**Wie löschen?**
```bash
DELETE /api/v1/users/me?confirmation=DELETE MY ACCOUNT
```

---

### 2. **Bot-Einstellungen** (ERFORDERLICH für Bot-Funktion)

| Feld | Zweck | Löschbar? |
|------|-------|-----------|
| `guild_id` | Discord-Server-ID | ✅ Ja |
| `prefix` | Command-Präfix (z.B. `!`) | ✅ Ja |
| `language` | Bot-Sprache | ✅ Ja |
| `moderation_enabled` | Moderation an/aus | ✅ Ja |
| `log_channel_id` | Log-Kanal | ✅ Ja |
| `welcome_message` | Willkommensnachricht | ✅ Ja |

**Warum erforderlich?**
Der Bot muss wissen, welche Einstellungen für deinen Server gelten.

**Wie löschen?**
```bash
DELETE /api/v1/settings/{guild_id}
```

---

### 3. **Command-Konfiguration** (Optional)

| Feld | Zweck | Löschbar? |
|------|-------|-----------|
| `guild_id` | Server-ID | ✅ Ja |
| `command_name` | Command-Name | ✅ Ja |
| `enabled` | An/Aus-Status | ✅ Ja |

**Warum erforderlich?**
Nur wenn du Commands pro Server aktivieren/deaktivieren willst.

---

### 4. **API-Keys** (Optional, nur für Admins)

| Feld | Zweck | Löschbar? |
|------|-------|-----------|
| `name` | Key-Name | ✅ Ja |
| `key_hash` | Gehashter Key (nicht umkehrbar) | ✅ Ja |
| `created_at` | Erstellungsdatum | ✅ Ja |

**Warum erforderlich?**
Nur wenn du externe Tools per API anbinden willst.

---

## 🛠️ Minimale Konfiguration aktivieren

### Schritt 1: `.env` Datei erstellen

Kopiere `.env.minimal` nach `.env`:

```bash
cp .env.minimal .env
```

### Schritt 2: Wichtige Einstellungen setzen

```bash
# Audit Logging DEAKTIVIEREN
AUDIT_LOG_ENABLED=false

# Keine IP-Adressen speichern
STORE_IP_ADDRESSES=false

# Keine User-Agents speichern
STORE_USER_AGENTS=false

# Minimale Aufbewahrung (falls Audit Logs aktiviert)
AUDIT_LOG_RETENTION_DAYS=1
AUDIT_LOG_ANONYMIZE_AFTER_DAYS=0
```

### Schritt 3: Migration ausführen

```bash
cd /mnt/c/Users/Nicolas/PycharmProjects/DiscordBot
alembic upgrade head
```

Dies entfernt:
- API Key Nutzungsstatistiken (`last_used_at`, `usage_count`)

### Schritt 4: Bot & API neu starten

```bash
# API neu starten
python -m api.main

# Bot neu starten
python -m bot.main
```

---

## 🗑️ Daten manuell löschen

### Alle Audit Logs löschen (Admin)

```bash
POST /api/v1/audit/cleanup?days=0
```

### Eigenen Account + alle Daten löschen

```bash
DELETE /api/v1/users/me?confirmation=DELETE MY ACCOUNT
```

Dies löscht:
- ✅ Dein Benutzerkonto
- ✅ Alle deine Audit Logs
- ✅ Alle deine API Keys
- ✅ Alle deine Rollenzuordnungen

### Bot-Einstellungen für einen Server löschen

```bash
DELETE /api/v1/settings/{guild_id}
```

---

## 📥 Datenexport (GDPR-konform)

```bash
GET /api/v1/users/me/export
```

Gibt dir **alle** gespeicherten Daten als JSON zurück:
- Benutzerprofil
- Audit Logs (falls aktiviert)
- API Keys
- Rollen

---

## 🔍 Vergleich: Vorher vs. Jetzt

| Datentyp | Vorher | Jetzt (Minimal) |
|----------|--------|-----------------|
| Audit Logs | ❌ Unbegrenzt | ✅ **Deaktiviert** |
| IP-Adressen | ❌ Dauerhaft | ✅ **Nicht gespeichert** |
| User-Agents | ❌ Dauerhaft | ✅ **Nicht gespeichert** |
| API Nutzung | ❌ Tracking | ✅ **Kein Tracking** |
| Account-Löschung | ❌ Nicht möglich | ✅ **Jederzeit** |
| Datenexport | ❌ Nicht möglich | ✅ **Jederzeit** |

---

## ⚠️ Was kann NICHT deaktiviert werden?

Diese Daten sind **technisch notwendig** für die Bot-Funktion:

1. **Benutzerkonten** - Ohne Login keine Verwaltung
2. **Bot-Einstellungen** - Bot muss wissen, wie er auf deinem Server funktionieren soll
3. **Discord-IDs** - Discord benötigt diese für OAuth-Login

Aber: Diese Daten kannst du **jederzeit löschen** durch Account-Löschung.

---

## 📋 Checkliste: Minimale Datenspeicherung

- [ ] `.env.minimal` nach `.env` kopiert
- [ ] `AUDIT_LOG_ENABLED=false` gesetzt
- [ ] `STORE_IP_ADDRESSES=false` gesetzt
- [ ] `STORE_USER_AGENTS=false` gesetzt
- [ ] Migration ausgeführt: `alembic upgrade head`
- [ ] API neu gestartet
- [ ] Bot neu gestartet

---

## 🆘 Support

Bei Fragen zur Datenspeicherung:
1. Überprüfe diese Datei: `PRIVACY.md`
2. Überprüfe `.env` Konfiguration
3. Erstelle ein Issue auf GitHub

**Wichtig:** Mit der minimalen Konfiguration wird **fast keine** Aktivität protokolliert. Das ist gut für Datenschutz, aber schlecht für Debugging. Bei Problemen kannst du temporär Audit Logs aktivieren.
