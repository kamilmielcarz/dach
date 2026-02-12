from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import math

app = FastAPI()

def clamp(v, a, b):
    return max(a, min(b, v))

def calc_roof(span_m: float, angle_deg: float, eave_m: float,
              rafter_b_cm: float, rafter_h_cm: float, wallplate_w_cm: float,
              purlin_enabled: bool, purlin_h_m: float, purlin_s_m: float):
    ang = math.radians(angle_deg)
    half = span_m / 2.0

    # geometria podstawowa
    rise = half * math.tan(ang)                     # wysokość kalenicy nad murłatą
    rafter_len_no_eave = half / math.cos(ang)      # po osi, bez okapu
    rafter_len = (half + eave_m) / math.cos(ang)   # po osi, z okapem

    # kąty cięcia (uprośćmy: plumb = angle)
    plumb_cut_deg = angle_deg
    seat_cut_deg = 90 - angle_deg

    # zacios (birdsmouth) - ograniczamy do 1/3 wysokości krokwi
    rafter_h_m = rafter_h_cm / 100.0
    wallplate_w_m = wallplate_w_cm / 100.0
    depth = 0.33 * rafter_h_m

    # długość "siedziska" dla danej głębokości (po poziomie)
    # depth = seat * tan(angle)  => seat = depth / tan(angle)
    seat_len = depth / math.tan(ang)

    # ogranicz seat_len do szerokości murłaty (żeby nie wyszło absurdalnie)
    seat_len = min(seat_len, wallplate_w_m)

    # PŁATEW
    # Można podać albo purlin_h_m (wysokość od murłaty), albo purlin_s_m (odległość po krokwi)
    purlin = None
    if purlin_enabled:
        if purlin_s_m and purlin_s_m > 0:
            # punkt na krokwi w odległości s od murłaty (po osi krokwi)
            s = clamp(purlin_s_m, 0, rafter_len_no_eave)
            x = math.cos(ang) * s   # rzut poziomy od murłaty do punktu
            y = math.sin(ang) * s   # wysokość punktu
            purlin = {"mode": "s", "s_m": round(s, 3), "x_m": round(x, 3), "y_m": round(y, 3)}
        else:
            # wysokość purlin_h_m od murłaty (po pionie)
            y = clamp(purlin_h_m, 0, rise)
            # y = tan(angle) * x => x = y / tan(angle)
            x = y / math.tan(ang) if math.tan(ang) != 0 else 0
            # odległość po krokwi: s = x / cos(angle)
            s = x / math.cos(ang) if math.cos(ang) != 0 else 0
            purlin = {"mode": "h", "s_m": round(s, 3), "x_m": round(x, 3), "y_m": round(y, 3)}

    return {
        "input": {
            "span_m": span_m, "angle_deg": angle_deg, "eave_m": eave_m,
            "rafter_b_cm": rafter_b_cm, "rafter_h_cm": rafter_h_cm, "wallplate_w_cm": wallplate_w_cm,
            "purlin_enabled": purlin_enabled, "purlin_h_m": purlin_h_m, "purlin_s_m": purlin_s_m
        },
        "results": {
            "half_span_m": round(half, 3),
            "ridge_height_m": round(rise, 3),
            "rafter_len_no_eave_m": round(rafter_len_no_eave, 3),
            "rafter_len_with_eave_m": round(rafter_len, 3),
            "plumb_cut_deg": round(plumb_cut_deg, 2),
            "seat_cut_deg": round(seat_cut_deg, 2),
            "birdsmouth_depth_m": round(depth, 3),
            "birdsmouth_seat_len_m": round(seat_len, 3),
        },
        "purlin": purlin
    }

def svg_roof(data):
    # prosta grafika: skala do 600x320
    span = data["input"]["span_m"]
    angle = data["input"]["angle_deg"]
    eave = data["input"]["eave_m"]
    res = data["results"]
    purlin = data["purlin"]

    ang = math.radians(angle)
    half = span / 2.0
    rise = res["ridge_height_m"]

    # punkty w metrach (lewa murłata w (0,0))
    left = (0, 0)
    right = (span, 0)
    ridge = (half, rise)

    # okap (poziomy)
    left_eave = (-eave, 0)
    right_eave = (span + eave, 0)

    # skala do SVG
    W, H = 760, 360
    pad = 40
    max_x = span + 2*eave
    max_y = rise

    sx = (W - 2*pad) / max_x if max_x else 1
    sy = (H - 2*pad) / (max_y if max_y else 1)

    # żeby nie było “spłaszczone”, bierzemy min skali
    s = min(sx, sy)
    def tx(x): return pad + (x + eave) * s
    def ty(y): return H - pad - y * s

    # linie
    lines = []
    # połać lewa i prawa (od okapu do kalenicy)
    lines.append((left_eave, ridge))
    lines.append((ridge, right_eave))
    # linia murłat
    base_line = (left, right)

    # płatew – rysujemy linię poziomą na wysokości y_m od obu stron
    purlin_line = None
    if purlin:
        y = purlin["y_m"]
        # x od lewej i symetrycznie od prawej
        x = purlin["x_m"]
        p1 = (x, y)
        p2 = (span - x, y)
        purlin_line = (p1, p2)

    def svg_line(p1, p2, stroke="#111", width=3):
        return f'<line x1="{tx(p1[0])}" y1="{ty(p1[1])}" x2="{tx(p2[0])}" y2="{ty(p2[1])}" stroke="{stroke}" stroke-width="{width}" />'

    def svg_text(x, y, txt, size=14):
        return f'<text x="{x}" y="{y}" font-size="{size}" fill="#111" font-family="Arial">{txt}</text>'

    svg = [f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">']
    svg.append('<rect width="100%" height="100%" fill="#ffffff"/>')

    # dach
    for a,b in lines:
        svg.append(svg_line(a,b, stroke="#111", width=4))
    svg.append(svg_line(base_line[0], base_line[1], stroke="#444", width=3))

    # płatew
    if purlin_line:
        svg.append(svg_line(purlin_line[0], purlin_line[1], stroke="#0b6", width=4))

    # opisy
    svg.append(svg_text(20, 28, f"Dach dwuspadowy | span={span}m | kąt={angle}° | okap={eave}m", 16))
    svg.append(svg_text(20, 52, f"Wys. kalenicy: {res['ridge_height_m']} m | Dł. krokwi (bez okapu): {res['rafter_len_no_eave_m']} m | z okapem: {res['rafter_len_with_eave_m']} m", 14))
    if purlin:
        svg.append(svg_text(20, 76, f"Płatew: wysokość {purlin['y_m']} m | od murłaty w poziomie {purlin['x_m']} m | po krokwi {purlin['s_m']} m", 14))

    svg.append('</svg>')
    return "\n".join(svg)

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
    <head>
      <meta charset="utf-8"/>
      <meta name="viewport" content="width=device-width, initial-scale=1"/>
      <title>Kalkulator ciesielski – dach dwuspadowy</title>
      <style>
        body{font-family:Arial;margin:24px;max-width:980px}
        .grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
        label{display:block;font-size:13px;margin-bottom:4px}
        input{width:100%;padding:10px;border:1px solid #ddd;border-radius:10px}
        .row{margin-bottom:12px}
        .card{border:1px solid #eee;border-radius:16px;padding:16px;box-shadow:0 2px 12px rgba(0,0,0,.05)}
        button{padding:12px 16px;border-radius:12px;border:0;background:#111;color:#fff;font-weight:700;cursor:pointer}
        .muted{color:#666;font-size:13px}
        .full{grid-column:1 / -1}
        .ok{color:#0b6;font-weight:700}
      </style>
    </head>
    <body>
      <h2>Kalkulator ciesielski – dach dwuspadowy (z opcją płatwi)</h2>
      <p class="muted">Wpisz dane i kliknij „Policz”. Wynik pokaże tabelę + rysunek. (Wersja startowa – geometria)</p>

      <div class="card">
        <form action="/view" method="get">
          <div class="grid">
            <div class="row">
              <label>Rozpiętość (murłata–murłata) [m]</label>
              <input name="span_m" value="10" />
            </div>
            <div class="row">
              <label>Kąt połaci [°]</label>
              <input name="angle_deg" value="35" />
            </div>
            <div class="row">
              <label>Okap (wysięg poziomy) [m]</label>
              <input name="eave_m" value="0.5" />
            </div>
            <div class="row">
              <label>Szerokość murłaty [cm]</label>
              <input name="wallplate_w_cm" value="14" />
            </div>
            <div class="row">
              <label>Krokiew – szerokość [cm]</label>
              <input name="rafter_b_cm" value="8" />
            </div>
            <div class="row">
              <label>Krokiew – wysokość [cm]</label>
              <input name="rafter_h_cm" value="20" />
            </div>

            <div class="row full">
              <label><b>Płatew (opcjonalnie)</b> — włącz 1 = tak, 0 = nie</label>
              <input name="purlin_enabled" value="1" />
              <div class="muted">Ustaw albo wysokość płatwi od murłaty (purlin_h_m), albo odległość po krokwi (purlin_s_m). Jeśli podasz oba, użyje purlin_s_m.</div>
            </div>
            <div class="row">
              <label>Płatew: wysokość od murłaty [m]</label>
              <input name="purlin_h_m" value="1.2" />
            </div>
            <div class="row">
              <label>Płatew: odległość po krokwi od murłaty [m]</label>
              <input name="purlin_s_m" value="0" />
            </div>
          </div>

          <div style="margin-top:14px">
            <button type="submit">Policz</button>
          </div>
        </form>
      </div>
    </body>
    </html>
    """

@app.get("/api/calc")
def api_calc(span_m: float = 10, angle_deg: float = 35, eave_m: float = 0.5,
             rafter_b_cm: float = 8, rafter_h_cm: float = 20, wallplate_w_cm: float = 14,
             purlin_enabled: int = 0, purlin_h_m: float = 0, purlin_s_m: float = 0):
    data = calc_roof(
        span_m, angle_deg, eave_m,
        rafter_b_cm, rafter_h_cm, wallplate_w_cm,
        bool(purlin_enabled), purlin_h_m, purlin_s_m
    )
    return data

@app.get("/view", response_class=HTMLResponse)
def view(span_m: float = 10, angle_deg: float = 35, eave_m: float = 0.5,
         rafter_b_cm: float = 8, rafter_h_cm: float = 20, wallplate_w_cm: float = 14,
         purlin_enabled: int = 0, purlin_h_m: float = 0, purlin_s_m: float = 0):
    data = calc_roof(
        span_m, angle_deg, eave_m,
        rafter_b_cm, rafter_h_cm, wallplate_w_cm,
        bool(purlin_enabled), purlin_h_m, purlin_s_m
    )
    res = data["results"]
    purlin = data["purlin"]
    svg = svg_roof(data)

    purlin_html = ""
    if purlin:
        purlin_html = f"""
        <div class="card">
          <h3>Płatew <span class="ok">włączona</span></h3>
          <ul>
            <li>Wysokość płatwi nad murłatą: <b>{purlin['y_m']} m</b></li>
            <li>Odległość w poziomie od murłaty: <b>{purlin['x_m']} m</b></li>
            <li>Odległość po krokwi od murłaty: <b>{purlin['s_m']} m</b></li>
          </ul>
        </div>
        """

    return f"""
    <html>
    <head>
      <meta charset="utf-8"/>
      <meta name="viewport" content="width=device-width, initial-scale=1"/>
      <title>Wyniki – dach dwuspadowy</title>
      <style>
        body{{font-family:Arial;margin:24px;max-width:1100px}}
        .grid{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}
        .card{{border:1px solid #eee;border-radius:16px;padding:16px;box-shadow:0 2px 12px rgba(0,0,0,.05)}}
        table{{width:100%;border-collapse:collapse}}
        td{{padding:10px;border-bottom:1px solid #f0f0f0}}
        .muted{{color:#666;font-size:13px}}
        a{{color:#111}}
        .btn{{display:inline-block;padding:10px 14px;border-radius:12px;background:#111;color:#fff;text-decoration:none;font-weight:700}}
      </style>
    </head>
    <body>
      <a class="btn" href="/">← Zmień dane</a>
      <h2>Wyniki – dach dwuspadowy</h2>
      <p class="muted">Geometria + zacios + opcjonalna płatew (wersja startowa).</p>

      <div class="grid">
        <div class="card">
          <h3>Wymiary i kąty</h3>
          <table>
            <tr><td>Połowa rozpiętości</td><td><b>{res['half_span_m']} m</b></td></tr>
            <tr><td>Wysokość kalenicy nad murłatą</td><td><b>{res['ridge_height_m']} m</b></td></tr>
            <tr><td>Długość krokwi (bez okapu)</td><td><b>{res['rafter_len_no_eave_m']} m</b></td></tr>
            <tr><td>Długość krokwi (z okapem)</td><td><b>{res['rafter_len_with_eave_m']} m</b></td></tr>
            <tr><td>Kąt cięcia przy kalenicy (plumb)</td><td><b>{res['plumb_cut_deg']}°</b></td></tr>
            <tr><td>Kąt „seat” (murłata)</td><td><b>{res['seat_cut_deg']}°</b></td></tr>
          </table>
        </div>

        <div class="card">
          <h3>Zacios (birdsmouth)</h3>
          <table>
            <tr><td>Głębokość zaciosu (max 1/3 h krokwi)</td><td><b>{res['birdsmouth_depth_m']} m</b></td></tr>
            <tr><td>Długość siedziska (ograniczona do murłaty)</td><td><b>{res['birdsmouth_seat_len_m']} m</b></td></tr>
          </table>
          <p class="muted">To jest baza do trasowania. W kolejnym kroku dodamy warianty wg PN-EN: śnieg/wiatr/zaspy + PDF.</p>
        </div>

        <div class="card" style="grid-column:1 / -1;">
          <h3>Rysunek (SVG)</h3>
          {svg}
        </div>

        {purlin_html}

        <div class="card" style="grid-column:1 / -1;">
          <h3>API</h3>
          <div class="muted">Te same dane w JSON:</div>
          <div><a href="/api/calc?span_m={span_m}&angle_deg={angle_deg}&eave_m={eave_m}&rafter_b_cm={rafter_b_cm}&rafter_h_cm={rafter_h_cm}&wallplate_w_cm={wallplate_w_cm}&purlin_enabled={purlin_enabled}&purlin_h_m={purlin_h_m}&purlin_s_m={purlin_s_m}">/api/calc (link)</a></div>
        </div>
      </div>
    </body>
    </html>
    """
