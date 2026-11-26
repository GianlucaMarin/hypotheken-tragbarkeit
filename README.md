# Hypotheken-Tragbarkeit API

FastAPI-Service, der die Tragbarkeit einer Hypothek nach Schweizer Standard berechnet:
Belehnung, kalkulatorische Wohnkosten (Zins, Nebenkosten, Amortisation) und ob die Wohnkosten
höchstens ein Drittel des Bruttoeinkommens ausmachen, bei mindestens 20 % Eigenkapital.

Live: https://hypotheken-tragbarkeit.onrender.com/docs (Render Free Tier: der erste Aufruf nach
einer Pause kann rund eine Minute dauern).

## Endpoints

| Methode | Pfad | Beschreibung |
|---------|------|--------------|
| GET | `/` | Leitet auf `/docs` weiter |
| GET | `/docs` | Swagger-Doku |
| POST | `/tragbarkeit-check` | Berechnung. Pflichtfelder: `einkommen_brutto_jahr`, `kaufpreis`, `eigenkapital`. Optional: `kalk_zins` (0.05), `nebenkosten_satz` (0.01), `amortisation_jahre` (15). Ungültige Eingaben ergeben HTTP 422. |

```bash
curl -X POST https://hypotheken-tragbarkeit.onrender.com/tragbarkeit-check -H 'Content-Type: application/json' -d '{"einkommen_brutto_jahr":150000,"kaufpreis":800000,"eigenkapital":200000}'
```

## Abhängigkeiten

| Datei | Wofür | Installation |
|-------|-------|--------------|
| `requirements.txt` | **Render / Produktion**: nur die API (20 Pakete) | `pip install -r requirements.txt` |
| `requirements-dev.txt` | **Lokal**: API + Notebooks + `Code/daten_erstellen.py` (71 Pakete) | `pip install --require-hashes -r requirements-dev.txt` |

Beide Dateien sind generiert, mit festen Versionen und SHA-256-Hashes für Python 3.13. Geändert
werden nur `requirements.in` bzw. `requirements-dev.in`. Wie man danach neu kompiliert und prüft,
steht in [SUPPLY_CHAIN.md](SUPPLY_CHAIN.md).

## Lokal starten

Python 3.13 verwenden, wie auf Render (`.python-version`). Falls `uv python find 3.13` nichts
findet, zuerst `uv python install 3.13` ausführen. `--clear` ersetzt eine bestehende `.venv`
vollständig, auch eine mit einer anderen Python-Version. Danach in VS Code den Kernel `.venv`
neu auswählen und, falls benötigt, pip-audit neu installieren (siehe SUPPLY_CHAIN.md).

```bash
"$(uv python find 3.13)" -m venv --clear .venv
.venv/bin/pip install --require-hashes -r requirements-dev.txt
.venv/bin/uvicorn Code.main:app --reload
```

Danach läuft die API unter http://127.0.0.1:8000/docs. Die Notebooks in `Code/` verwenden
dieselbe `.venv` als Kernel.

## Deployment (Render)

Render baut bei jedem Push auf `main` automatisch neu. Es installiert `requirements.txt`, wobei
pip die Hashes automatisch prüft, und verwendet die Python-Version aus `.python-version`. Der
Start-Befehl ist im Render-Dashboard konfiguriert (z.B. `uvicorn Code.main:app --host 0.0.0.0 --port $PORT`).

## Sicherheit

Schwachstellen-Scan, Hash-Prüfung, Dependabot und Secret-Check: siehe
[SUPPLY_CHAIN.md](SUPPLY_CHAIN.md). Der Azure-Endpoint-Key (`Code/endpoint_key.txt`) wird nie
committet.
