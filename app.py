from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import math

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <h2>Kalkulator Dachu</h2>
    <form action="/oblicz">
        Rozpiętość (m): <input name="span"><br>
        Kąt (°): <input name="angle"><br>
        <button type="submit">Oblicz</button>
    </form>
    """

@app.get("/oblicz")
def oblicz(span: float, angle: float):
    half = span / 2
    rad = math.radians(angle)
    length = half / math.cos(rad)

    return {
        "dlugosc_krokwi_m": round(length, 2),
        "strefa_sniegowa": "II",
        "sk_kN_m2": 0.9
    }
