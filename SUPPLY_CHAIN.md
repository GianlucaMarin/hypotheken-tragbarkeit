# Supply-Chain-Sicherheit (OWASP LLM04)

Die API selbst besteht aus zwei Python-Dateien, hängt aber von fremden Paketen ab. Wird eines
davon verwundbar, manipuliert oder unbemerkt ausgetauscht, läuft der fremde Code mit derselben
Berechtigung wie unsere API auf render.com. Deshalb sind die Abhängigkeiten in zwei Ebenen
getrennt:

| Ebene | Datei | Inhalt | Pakete |
|-------|-------|--------|--------|
| **Render (Produktion)** | `requirements.txt` | nur, was die API braucht: `fastapi`, `pydantic`, `uvicorn[standard]` | **20** (3 direkte + 17 Unterpakete) |
| **Entwicklung (lokal)** | `requirements-dev.txt` | API + Notebooks + `Code/daten_erstellen.py`: zusätzlich `ipykernel`, `requests`, `certifi`, `pandas`, `matplotlib`, `plotly`, `nbformat` | 71 (davon dieselben 20 wie oben, in derselben Version) |

Auf Render landet damit nur noch ein kleiner Teil der Pakete: die Jupyter- und Daten-Pakete sind
nicht mehr Teil der Angriffsfläche des Servers. Die folgenden vier Prüfungen sichern beide
Ebenen ab.

| # | Prüfung | Dateien | Warum |
|---|---------|---------|-------|
| 1 | Schwachstellen-Scan | `requirements.txt`, `requirements-dev.txt` | Findet bekannte Sicherheitslücken (CVE/GHSA/PYSEC) in den genutzten Versionen. |
| 2 | Feste Versionen + SHA-256-Hashes | `requirements.in` → `requirements.txt`, `requirements-dev.in` → `requirements-dev.txt` | Installiert wird genau das, was geprüft wurde. Ein manipuliertes oder ausgetauschtes Paket hat einen anderen Hash, und pip bricht die Installation ab. |
| 3 | Laufende Überwachung | `.github/dependabot.yml`, Dependabot-Alerts (GitHub) | Neue Lücken werden auch nach dem Deploy erkannt. Alerts gelten für alle Pakete beider Dateien, Update-PRs kommen wöchentlich. |
| 4 | Secret-Check | `.gitignore`, `Code/endpoint_key.txt` | Der Azure-Endpoint-Key darf nie im öffentlichen Repo landen, auch nicht in der Git-History. |

Alle Befehle werden im Repo-Root ausgeführt. Die Code-Blöcke enthalten absichtlich keine
`#`-Kommentare: In einer interaktiven zsh ohne `interactivecomments` würden diese als Argumente
gelesen.

## 1. Schwachstellen-Scan (pip-audit)

`pip-audit` wird nur in der lokalen `.venv` installiert. Es gehört in keine der Requirements-Dateien,
weil es zum Prüfen dient und nicht zum Betrieb. Auch die Prüfwerkzeuge gehören zur Lieferkette,
deshalb sind ihre Versionen in den Befehlen fest (`pip-audit==2.10.1`, `pip-tools==7.7.0`).

```bash
.venv/bin/pip install pip-audit==2.10.1
.venv/bin/pip-audit -r requirements.txt --desc --require-hashes --disable-pip
.venv/bin/pip-audit -r requirements-dev.txt --desc --require-hashes --disable-pip
```

Diese Variante prüft exakt die gelockten Versionen (20 bzw. 71 Pakete), ohne neu aufzulösen.
Erwartet wird zweimal `No known vulnerabilities found` mit Exit-Code 0. Die kürzere Variante
ohne `--require-hashes --disable-pip` löst die Abhängigkeiten mit dem Python der `.venv` neu auf
und kann dabei einzelne Pakete auslassen.

Bei einem Fund nennt pip-audit die gefixte Version:

- **Direkte Abhängigkeit** (steht in `requirements.in` oder `requirements-dev.in`): Version dort
  anheben und beide Dateien neu kompilieren (siehe 2).
- **Unterpaket**: gezielt anheben, zum Beispiel `idna` auf die neueste Version. Für eine
  bestimmte Version schreibt man `idna==X.Y.Z`. Steht das Paket in `requirements.txt`, zuerst
  dort anheben (erste Zeile), dann die Dev-Datei nachziehen (zweite Zeile). Steht es nur in
  `requirements-dev.txt`, reicht die zweite Zeile mit `--upgrade-package`.

```bash
uvx --python 3.13 --from pip-tools==7.7.0 pip-compile --generate-hashes --allow-unsafe --upgrade-package idna requirements.in
uvx --python 3.13 --from pip-tools==7.7.0 pip-compile --generate-hashes --allow-unsafe requirements-dev.in
```

Danach erneut scannen und die Tests aus Abschnitt 2 wiederholen.

## 2. Integrität per Hash (pip-compile)

- `requirements.in` und `requirements-dev.in` enthalten nur die direkten Abhängigkeiten. Sie
  werden **von Hand gepflegt**.
- `requirements.txt` und `requirements-dev.txt` werden daraus **generiert** (nicht von Hand
  bearbeiten). Sie enthalten alle Pakete mit fester Version und den SHA-256-Hashes aller Wheels
  jeder Version.
- `requirements-dev.in` bindet mit `-r requirements.in` die API ein und mit `-c requirements.txt`
  die Render-Versionen als Vorgabe. Gemeinsame Pakete haben dadurch lokal **genau dieselbe
  Version wie auf Render**. Die Zeile `-r requirements.in` nicht entfernen: Dependabot bestimmt
  nur über `-r` die Reihenfolge, in der es die Dateien kompiliert.
- `--only-binary :all:` (steht in allen vier Dateien bzw. wird per `-r` übernommen): pip
  installiert nur fertige Wheels und baut nie aus Quellcode. Sonst könnte pip Build-Werkzeuge wie
  setuptools nachladen, und die werden nicht per Hash geprüft. Meldet pip
  `No matching distribution found`, gibt es für diese Version kein passendes Wheel (Linux bzw.
  Python 3.13). Dann eine andere Version wählen.

Sobald eine Zeile einen Hash hat, schaltet pip automatisch in den Hash-Prüfmodus. Render prüft
die Hashes also beim normalen `pip install -r requirements.txt` mit. Aufgelöst wird für
Python 3.13, so wie es `.python-version` für Render festlegt.

Beide Dateien neu erzeugen, nach jeder Änderung an einer `.in`-Datei und immer in dieser
Reihenfolge, weil die Dev-Datei auf `requirements.txt` aufbaut:

```bash
uvx --python 3.13 --from pip-tools==7.7.0 pip-compile --generate-hashes --allow-unsafe requirements.in
uvx --python 3.13 --from pip-tools==7.7.0 pip-compile --generate-hashes --allow-unsafe requirements-dev.in
```

**Render-Ebene** in einer frischen Python-3.13-venv testen (falls `uv python find 3.13` nichts
findet, zuerst `uv python install 3.13` ausführen):

```bash
"$(uv python find 3.13)" -m venv /tmp/sc-venv
/tmp/sc-venv/bin/pip install --require-hashes -r requirements.txt
/tmp/sc-venv/bin/uvicorn Code.main:app --port 8765 &
for i in $(seq 40); do curl -s -o /dev/null http://127.0.0.1:8765/docs && break; sleep 0.5; done
curl -sS --fail -X POST http://127.0.0.1:8765/tragbarkeit-check -H 'Content-Type: application/json' -d '{"einkommen_brutto_jahr":150000,"kaufpreis":800000,"eigenkapital":200000}'
kill $!; rm -rf /tmp/sc-venv
```

Erwartet wird `{"hypothek":600000.0, … "tragbarkeit_prozent":28.3,"tragbar":true,"hinweise":[]}`.
Erscheint vorher eine `ERROR`-Zeile, ist der Test fehlgeschlagen, auch wenn danach JSON kommt
(zum Beispiel von einem alten Server, der noch auf Port 8765 läuft).

**Entwicklungs-Ebene** testen:

```bash
"$(uv python find 3.13)" -m venv /tmp/sc-dev
/tmp/sc-dev/bin/pip install --require-hashes -r requirements-dev.txt
/tmp/sc-dev/bin/python -c "import ipykernel, requests, certifi, pandas, matplotlib, plotly, nbformat, fastapi; print('OK')"
rm -rf /tmp/sc-dev
```

Erwartet wird `OK` ohne vorherige `ERROR`-Zeile.

**Plattform-Hinweis:** Die Locks werden auf macOS erzeugt, Dependabot kompiliert auf Linux.
Beide ergeben dieselben Dateien. `requirements.txt` enthält keine macOS-spezifischen Pakete.
In `requirements-dev.in` ist `appnope` (eine macOS-Abhängigkeit von ipykernel) bewusst ohne
Plattform-Marker gepinnt. So entfernt Dependabot es nicht, und die Dev-Installation
funktioniert auf macOS und Linux. Auf Linux wird es mitinstalliert, ist dort aber wirkungslos.

## 3. Laufende Überwachung (Dependabot)

- `.github/dependabot.yml` prüft jeden Montag das `pip`-Ökosystem im Repo-Root. Dependabot
  erkennt dort **beide** Paare (`requirements.in`/`.txt` und `requirements-dev.in`/`.txt`),
  öffnet Update-PRs für die direkten Abhängigkeiten und kompiliert dabei die betroffenen
  `.txt`-Dateien samt Hashes neu.
- Die **Dependabot-Alerts** sind für das Repo aktiviert und gelten für alle Pakete beider
  Dateien, auch für die Unterpakete. Bei einem Alert für ein Unterpaket wird es wie in
  Abschnitt 1 gezielt angehoben. Wer dafür automatische PRs will, kann unter
  *Settings → Code security* die *Dependabot security updates* einschalten.
- Kann Dependabot ein Update nicht erstellen, hält meist ein Dev-Paket ein gemeinsames Paket
  zurück, denn beide Dateien müssen dieselbe Version haben. Dann das Update lokal mit den
  Befehlen aus Abschnitt 1 erstellen.

Status prüfen:

```bash
gh api repos/GianlucaMarin/hypotheken-tragbarkeit/vulnerability-alerts -i | head -1
gh api 'repos/GianlucaMarin/hypotheken-tragbarkeit/dependabot/alerts?state=open&per_page=100' --jq 'length'
gh api repos/GianlucaMarin/hypotheken-tragbarkeit/dependency-graph/sbom --jq '[.sbom.packages[] | select(.name | startswith("com.github.") | not) | .name] | unique | length'
```

Die erste Zeile muss `HTTP/2.0 204 No Content` zeigen (204 = aktiv, 404 = aus). Die zweite
zeigt die Anzahl offener Alerts, erwartet wird 0. Die dritte zeigt, wie viele verschiedene
Pakete GitHub überwacht, erwartet wird 71 (alle Pakete der Dev-Datei, die die 20 Render-Pakete
enthält).

## 4. Secret-Check (Endpoint-Key)

Diese Befehle geben den Key nie aus, sondern nur Pfade und Zähler:

```bash
[ -n "$(LC_ALL=C tr -cd '[:graph:]' < Code/endpoint_key.txt)" ] && echo "Key-Datei vorhanden" || echo "Key-Datei FEHLT oder leer, Inhaltssuche nicht aussagekraeftig"
git check-ignore -v Code/endpoint_key.txt
git log --all --full-history --oneline -- Code/endpoint_key.txt | wc -l
git rev-list --all --objects | grep -c endpoint_key
git log --all --reflog -p --text --diff-merges=first-parent | grep -c -F -f <(LC_ALL=C tr -cd '[:graph:]' < Code/endpoint_key.txt)
```

Erwartet wird:

1. `Key-Datei vorhanden`
2. die `.gitignore`-Regel
3. `0`
4. `0`
5. `0`

Zeile 5 sucht den Key-*Inhalt* in jeder Version jeder Datei der gesamten History, auch in
Merge-Commits. Leerzeichen, Zeilenumbrüche und ein BOM in der Key-Datei werden dabei ignoriert. Die
`.gitignore` ignoriert zusätzlich `endpoint_key*` in jedem Ordner sowie `.env`-Dateien.

Falls der Key doch einmal committet wurde, reicht Löschen nicht. Dann den Key in Azure
**sofort neu generieren**, weil er öffentlich war, und erst danach die History bereinigen.
