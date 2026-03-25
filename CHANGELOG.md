# Changelog

## [Unreleased]

### Fixed — sync_from_modules.py: metadata.json auch ohne Docker-Images schreiben (2026-03-25)

- `_sync_one_module`: Bei fehlendem lokalen Docker-Image (`RuntimeError`) wurde bisher mit
  `return None` abgebrochen und `metadata.json` nie geschrieben. Jetzt wird die Warnung
  ausgegeben und `metadata.json` ohne `images`-Einträge geschrieben.
- Skip-Logik ("kein Update" / "identisch") prüft jetzt zusätzlich ob `metadata.json`
  existiert. Fehlt sie, wird das Modul immer vollständig synchronisiert — auch wenn das
  tar.gz noch aktuell ist.
