"""Erstellt den Zeitreihen-Datensatz Daten/hypozins_usa.csv für Azure AutoML.

Quelle: FRED (Federal Reserve Bank of St. Louis), CSV-Download ohne API-Key.
Eine Zeile pro Woche, Datum = Donnerstag (Veröffentlichungstag von MORTGAGE30US).
Aufruf im Projektordner: source .venv/bin/activate && python3 Code/daten_erstellen.py
"""

import io
import time
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pandas as pd
import requests

FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
START = "2000-01-01"
ZIEL = Path(__file__).resolve().parent.parent / "Daten" / "hypozins_usa.csv"


def lade_fred(serie: str) -> pd.Series:
    """Lädt eine FRED-Serie (Index = Datum, fehlende Werte = NaN), mit 3 Versuchen."""
    for versuch in range(1, 4):
        try:
            antwort = requests.get(FRED_URL, params={"id": serie}, timeout=60)
            antwort.raise_for_status()
            break
        except requests.RequestException:
            if versuch == 3:
                raise
            time.sleep(5 * versuch)
    df = pd.read_csv(io.StringIO(antwort.text), index_col=0, parse_dates=True, na_values=".")
    return df[serie].astype(float)


def wochenmittel(taeglich: pd.Series) -> pd.Series:
    """Tageswerte -> Mittelwert pro Woche Freitag bis Donnerstag, Label = Donnerstag."""
    return taeglich.resample("W-THU", closed="right", label="right").mean()


def runden(wert: float) -> float:
    """Kaufmännisch auf 2 Stellen runden (4.575 -> 4.58), unabhängig von Fliesskomma-Ungenauigkeit."""
    gerundet = Decimal(f"{wert:.9f}").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return float(gerundet) + 0.0  # + 0.0 macht aus -0.00 ein 0.00


def monatlich(serie: pd.Series) -> pd.Series:
    """Lückenloses Monatsraster; einzelne fehlende Monate (z.B. Okt. 2025, Shutdown) linear füllen."""
    return serie.asfreq("MS").interpolate(limit_area="inside")


# Zielwert: 30-jähriger Hypothekarzins. FRED datiert ihn bis 2003 auf Freitag und in
# Feiertagswochen auf Mittwoch -> auf den Donnerstag derselben Woche schieben.
hypo = lade_fred("MORTGAGE30US").dropna()
donnerstag = hypo.index + pd.to_timedelta((6 - hypo.index.day_of_week) % 7 - 3, unit="D")
behalten = donnerstag >= START
verschoben = (donnerstag != hypo.index)[behalten].sum()
print(f"MORTGAGE30US: {verschoben} von {behalten.sum()} Daten auf Donnerstag verschoben")
hypo = hypo.set_axis(donnerstag)[behalten]

# Nur vollständige Wochen: die Tagesdaten müssen bis zum Donnerstag reichen
# (Feiertage führt FRED als leere Zeilen, sie zählen als gemeldete Tage mit)
dgs10, dff = lade_fred("DGS10"), lade_fred("DFF")
tagesdaten_bis = min(dgs10.index.max(), dff.index.max())
unvollstaendig = hypo.index[hypo.index > tagesdaten_bis]
if len(unvollstaendig):
    print(f"Unvollständige Woche entfernt: {', '.join(unvollstaendig.strftime('%Y-%m-%d'))} "
          f"(Tagesdaten erst bis {tagesdaten_bis:%Y-%m-%d})")
hypo = hypo[hypo.index <= tagesdaten_bis]
wochen = hypo.index

# Monatswerte: Inflation = Veränderung des CPI gegenüber Vorjahresmonat in %
cpi = monatlich(lade_fred("CPIAUCSL"))
inflation = (cpi / cpi.shift(12) - 1) * 100
arbeitslosenquote = monatlich(lade_fred("UNRATE"))

df = pd.DataFrame(
    {
        "hypozins_30j": hypo,
        "rendite_10j": wochenmittel(dgs10).reindex(wochen),
        "leitzins": wochenmittel(dff).reindex(wochen),
        # Monatswert gilt ab dem 1. des Monats und wird auf die Wochen vorwärts aufgefüllt
        "inflation": inflation.dropna().reindex(wochen, method="ffill"),
        "arbeitslosenquote": arbeitslosenquote.dropna().reindex(wochen, method="ffill"),
    },
    index=wochen,
)
df.index.name = "datum"

# Prüfungen: keine leeren Werte, keine doppelten oder fehlenden Wochen
leere_werte = df.isna().sum()
abstaende = df.index.to_series().diff().dropna()
fehlende_wochen = int((abstaende / pd.Timedelta(days=7) - 1).sum())
duplikate = int(df.index.duplicated().sum())
if leere_werte.any() or fehlende_wochen or duplikate:
    raise SystemExit(
        f"Datensatz unvollständig - leere Werte:\n{leere_werte}\n"
        f"fehlende Wochen: {fehlende_wochen}, doppelte Wochen: {duplikate}"
    )

# Auf 2 Nachkommastellen runden und speichern
df = df.map(runden)
ZIEL.parent.mkdir(exist_ok=True)
df.to_csv(ZIEL, float_format="%.2f", date_format="%Y-%m-%d")

print(f"Gespeichert: {ZIEL}")
print(f"Anzahl Zeilen: {len(df)} ({df.index[0]:%Y-%m-%d} bis {df.index[-1]:%Y-%m-%d})")
print(f"\nErste 5 Zeilen:\n{df.head().to_string(float_format='%.2f')}")
print(f"\nLetzte 5 Zeilen:\n{df.tail().to_string(float_format='%.2f')}")
print(f"\nLeere Werte: {int(leere_werte.sum())}, fehlende Wochen: {fehlende_wochen}, doppelte Wochen: {duplikate}")
