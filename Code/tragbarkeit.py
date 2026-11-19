"""Business-Logik: Tragbarkeitsrechnung für Hypotheken nach Schweizer Standard."""

TRAGBARKEIT_LIMIT = 1 / 3      # Wohnkosten max. 1/3 des Bruttoeinkommens
EIGENKAPITAL_MIN = 0.20        # mind. 20 % Eigenkapital
ERSTE_HYPOTHEK_ANTEIL = 2 / 3  # Belehnung bis 2/3 muss nicht amortisiert werden


def berechne_tragbarkeit(
    einkommen_brutto_jahr: float,
    kaufpreis: float,
    eigenkapital: float,
    kalk_zins: float = 0.05,
    nebenkosten_satz: float = 0.01,
    amortisation_jahre: int = 15,
) -> dict:
    """Berechnet Tragbarkeit und Belehnung und gibt alle Zwischenwerte zurück."""
    # Eingaben prüfen
    if min(einkommen_brutto_jahr, kaufpreis, eigenkapital, kalk_zins,
           nebenkosten_satz, amortisation_jahre) <= 0:
        raise ValueError("Alle Beträge müssen grösser als 0 sein.")
    if eigenkapital >= kaufpreis:
        raise ValueError("Eigenkapital muss kleiner als der Kaufpreis sein.")

    # Hypothek und Belehnung
    hypothek = kaufpreis - eigenkapital
    belehnung = hypothek / kaufpreis

    # Jährliche Wohnkosten: kalk. Zins + Nebenkosten + Amortisation (2. Hypothek)
    zinskosten = hypothek * kalk_zins
    nebenkosten = kaufpreis * nebenkosten_satz
    amortisation = max(0.0, hypothek - kaufpreis * ERSTE_HYPOTHEK_ANTEIL) / amortisation_jahre
    wohnkosten_jahr = zinskosten + nebenkosten + amortisation

    # Tragbarkeit = Anteil der Wohnkosten am Bruttoeinkommen
    tragbarkeit = wohnkosten_jahr / einkommen_brutto_jahr

    # Kriterien prüfen und Hinweise sammeln
    eigenkapital_ok = eigenkapital >= kaufpreis * EIGENKAPITAL_MIN
    tragbarkeit_ok = tragbarkeit <= TRAGBARKEIT_LIMIT
    hinweise = []
    if not eigenkapital_ok:
        hinweise.append("Eigenkapital unter 20%")
    if not tragbarkeit_ok:
        hinweise.append("Tragbarkeit über 33%")

    return {
        "hypothek": round(hypothek, 2),
        "belehnung_prozent": round(belehnung * 100, 1),
        "zinskosten": round(zinskosten, 2),
        "nebenkosten": round(nebenkosten, 2),
        "amortisation": round(amortisation, 2),
        "wohnkosten_jahr": round(wohnkosten_jahr, 2),
        "tragbarkeit_prozent": round(tragbarkeit * 100, 1),
        "tragbar": tragbarkeit_ok and eigenkapital_ok,
        "hinweise": hinweise,
    }
