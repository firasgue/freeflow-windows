# 🎙️ FreeFlow Windows

Kostenlose KI-Sprachtranskription für Windows — inspiriert von [zachlatta/freeflow](https://github.com/zachlatta/freeflow) (macOS).

**Taste halten → sprechen → loslassen → Text erscheint im aktiven Textfeld.**

Nutzt Groqs kostenlosen API-Key für Whisper-Transkription + LLM-Postprocessing (kontextbewusste Namenskorrektur, Füllwortbereinigung usw.).

---

## Schnellstart (EXE)

1. `build.bat` ausführen → `dist\FreeFlowWindows.exe` wird erstellt
2. EXE starten → Setup-Dialog erscheint
3. Kostenlosen Groq API-Key unter [console.groq.com](https://console.groq.com) holen und eintragen
4. Aufnahme-Taste wählen (Standard: Rechte Strg-Taste)
5. In ein beliebiges Textfeld klicken, Taste halten, sprechen, loslassen ✅

---

## Schnellstart (Python direkt)

```bash
pip install -r requirements.txt
python freeflow_windows.py
```

---

## Wie es funktioniert

1. **Taste halten** (≥300 ms) → Aufnahme startet (kurzer Ton)
2. **Sprechen**
3. **Taste loslassen** → Audio geht an Groq Whisper API
4. **LLM bereinigt** Transkript (Füllwörter, Interpunktion, Kontext-Korrekturen)
5. **Text wird eingefügt** via Strg+V in das aktive Textfeld

### Kontext-Bewusstsein

Das Script liest:
- **Fenstertitel** des aktiven Fensters (z. B. „Re: Angebot von Max Mustermann → Namen korrekt schreiben")
- **Zwischenablage** (ersten 500 Zeichen als Kontext)

---

## Einstellungen

Über Rechtsklick auf das Tray-Icon → **Einstellungen**, oder JSON direkt bearbeiten:

```
C:\Users\<Name>\.freeflow-windows\config.json
```

| Einstellung | Standard | Beschreibung |
|---|---|---|
| `api_key` | – | Groq API-Key |
| `hotkey` | `right ctrl` | Aufnahme-Taste |
| `post_processing` | `true` | LLM-Bereinigung an/aus |
| `groq_transcription_model` | `whisper-large-v3-turbo` | Whisper-Modell |
| `groq_llm_model` | `llama-3.3-70b-versatile` | LLM für Postprocessing |
| `custom_vocabulary` | `[]` | Eigene Begriffe/Namen |
| `hold_threshold_ms` | `300` | Mindest-Haltezeit in ms |

### Eigenes Vokabular

Im Einstellungen-Dialog: einen Begriff pro Zeile eintragen.  
Das LLM wird angewiesen, diese Schreibweisen beizubehalten (z. B. Firmennamen, Fachbegriffe).

---

## Hotkey-Empfehlungen

| Taste | Name in config |
|---|---|
| Rechte Strg | `right ctrl` |
| F9–F12 | `f9`, `f10`, `f11`, `f12` |
| Scroll Lock | `scroll lock` |
| Pause/Break | `pause` |

> **Hinweis:** Die `Fn`-Taste funktioniert unter Windows nicht als globaler Hotkey — sie wird direkt von der Firmware verarbeitet.

---

## Problembehebung

**Hotkey reagiert nicht:**  
→ App als Administrator starten (Rechtsklick → „Als Administrator ausführen")

**Kein Ton/Aufnahme:**  
→ Sicherstellen dass ein Mikrofon angeschlossen ist und Windows-Zugriff erlaubt ist

**API-Fehler 401:**  
→ Groq API-Key prüfen (Einstellungen)

**EXE startet nicht:**  
→ `python freeflow_windows.py` im Terminal starten für Fehlermeldungen

---

## Datenschutz

- Kein eigener Server — nur direkte API-Calls an Groq
- Lokale Konfiguration unter `~/.freeflow-windows/config.json`
- Audio wird nur während der Aufnahme im RAM gehalten, nie dauerhaft gespeichert

---

## Lizenz

MIT — basierend auf [zachlatta/freeflow](https://github.com/zachlatta/freeflow)
