"""FastAPI-App: stellt die Tragbarkeitsrechnung als REST-Endpoint bereit."""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .tragbarkeit import berechne_tragbarkeit

app = FastAPI(title="HypothekenTragbarkeitAPI")


class TragbarkeitInput(BaseModel):
    """Eingabedaten; gt=0 sorgt automatisch für HTTP 422 bei Werten <= 0."""
    einkommen_brutto_jahr: float = Field(gt=0)
    kaufpreis: float = Field(gt=0)
    eigenkapital: float = Field(gt=0)
    kalk_zins: float = Field(default=0.05, gt=0)
    nebenkosten_satz: float = Field(default=0.01, gt=0)
    amortisation_jahre: int = Field(default=15, gt=0)


class TragbarkeitOutput(BaseModel):
    """Antwort mit allen Zwischenwerten."""
    hypothek: float
    belehnung_prozent: float
    zinskosten: float
    nebenkosten: float
    amortisation: float
    wohnkosten_jahr: float
    tragbarkeit_prozent: float
    tragbar: bool
    hinweise: list[str]


@app.post("/tragbarkeit-check", response_model=TragbarkeitOutput)
def tragbarkeit_check(daten: TragbarkeitInput):
    # Fachliche Fehler (z.B. Eigenkapital >= Kaufpreis) ebenfalls als 422 melden
    try:
        return berechne_tragbarkeit(**daten.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
