from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import math

app = FastAPI()

def clamp(v, a, b):
    return max(a, min(b, v))

def fmt_cm(x): return f"{x:.1f} cm"
def fmt_deg(x): return f"{x:.2f}°"

# -------------------------
# Core calc (ALL in cm)
# Definitions:
# - Poziom x: od zewnętrznej krawędzi murłaty do środka
# - Pion y: w górę od górnej krawędzi murłaty
# -------------------------
def calc_roof_cm(
    span_cm: float,
    angle_deg: float,
    eave_out_cm: float,

    rafter_h_cm: float,       # wysokość krokwi (np. 20)
    wallplate_w_cm: float,    # szerokość murłaty (do opisu)
    wallplate_h_cm: float,    # wysokość murłaty (do liczenia "od dołu murłaty")

    # siodełko (w dół) - JEDNAKOWO dla murłaty i płatwi
    bearing_cm: float,        # 4 cm

    # PŁATEW
    purlin_enabled: bool,
    purlin_section_h_cm: float,              # wysokość płatwi (np. 20)
    purlin_s_from_outer_wallplate_cm: float, # opcjonalnie: odległość po krokwi
    purlin_top_above_wallplate_cm: float,    # wysokość GÓRY płatwi nad górą murłaty (gdy s=0)
):
    ang = math.radians(angle_deg)
    half_span_cm = span_cm / 2.0

    ridge_height_cm = half_span_cm * math.tan(ang)
    rafter_len_no_eave_cm = half_span_cm / math.cos(ang)
    rafter_len_with_eave_cm = (half_span_cm + eave_out_cm) / math.cos(ang)

    plumb_cut_deg = angle_deg
    seat_cut_deg = 90.0 - angle_deg

    # -------------------------
    # SIODŁO NA MURŁACIE (4 cm w dół)
    # -------------------------
    murlata_depth_cm = clamp(bearing_cm, 0, 0.33 * rafter_h_cm)
    murlata_seat_horiz_cm = (murlata_depth_cm / math.tan(ang)) if math.tan(ang) != 0 else 0.0
    murlata_seat_along_rafter_cm = (murlata_depth_cm / math.sin(ang)) if math.sin(ang) != 0 else 0.0

    # (opcjonalnie) żeby nie wyszło większe niż murłata
    murlata_seat_horiz_cm = min(murlata_seat_horiz_cm, wallplate_w_cm)

    # -------------------------
    # PŁATEW: pozycja + siodełko (4 cm w dół)
    # -------------------------
    purlin = None
    if purlin_enabled:
        # wyznacz punkt (x, y_top) dla GÓRY płatwi
        if purlin_s_from_outer_wallplate_cm and purlin_s_from_outer_wallplate_cm > 0:
            s = clamp(purlin_s_from_outer_wallplate_cm, 0, rafter_len_no_eave_cm)
            x = math.cos(ang) * s
            y_top = math.sin(ang) * s
            mode = "po_krokwi"
        else:
            y_top = clamp(purlin_top_above_wallplate_cm, 0, ridge_height_cm)
            x = y_top / math.tan(ang) if math.tan(ang) != 0 else 0.0
            s = x / math.cos(ang) if math.cos(ang) != 0 else 0.0
            mode = "po_wysokosci_gory"

        y_bottom = y_top - purlin_section_h_cm

        # dół płatwi od dołu murłaty (pod wieniec/poduszkę)
        bottom_from_bottom_wallplate_cm = wallplate_h_cm + y_bottom

        # siodełko pod płatew (4 cm w dół)
        purlin_notch_depth_cm = clamp(bearing_cm, 0, 0.33 * rafter_h_cm)
        purlin_notch_horiz_cm = (purlin_notch_depth_cm / math.tan(ang)) if math.tan(ang) != 0 else 0.0
        purlin_notch_along_rafter_cm = (purlin_notch_depth_cm / math.sin(ang)) if math.sin(ang) != 0 else 0.0

        purlin = {
            "mode": mode,
            "x_cm": x,                 # po poziomie od zewn. krawędzi murłaty w stronę środka
            "s_cm": s,                 # po krokwi
            "y_top_cm": y_top,         # góra płatwi nad górą murłaty
            "y_bottom_cm": y_bottom,   # dół płatwi nad górą murłaty
            "bottom_from_bottom_wallplate_cm": bottom_from_bottom_wallplate_cm,

            "purlin_section_h_cm": purlin_section_h_cm,

            "notch_depth_cm": purlin_notch_depth_cm,
            "notch_horiz_cm": purlin_notch_horiz_cm,
            "notch_along_rafter_cm": purlin_notch_along_rafter_cm,
        }

    return {
        "input": {
            "span_cm": span_cm,
            "angle_deg": angle_deg,
            "eave_out_cm": eave_out_cm,
            "rafter_h_cm": rafter_h_cm,
            "wallplate_w_cm": wallplate_w_cm,
            "wallplate_h_cm": wallplate_h_cm,
            "bearing_cm": bearing_cm,
            "purlin_enabled": purlin_enabled,
            "purlin_section_h_cm": purlin_section_h_cm,
            "purlin_s_from_outer_wallplate_cm": purlin_s_from_outer_wallplate_cm,
            "purlin_top_above_wallplate_cm": purlin_top_above_wallplate_cm,
        },
        "results": {
            "polowa_rozpietosci_cm": half_span_cm,
            "wysokosc_kalenicy_nad_gora_murlaty_cm": ridge_height_cm,
            "dlugosc_krokwi_po_osi_bez_okapu_cm": rafter_len_no_eave_cm,
            "dlugosc_krokwi_po_osi_z_okapem_cm": rafter_len_with_eave_cm,
            "kat_plumb_kalenica_deg": plumb_cut_deg,
            "kat_seat_murlata_deg": seat_cut_deg,

            "murlata_siodlo_w_dol_cm": murlata_depth_cm,
            "murlata_siodlo_poziomo_cm": murlata_seat_horiz_cm,
            "murlata_siodlo_po_krokwi_cm": murlata_seat_along_rafter_cm,
        },
        "purlin": purlin,
    }

# -------------------------
# SVG 1: przekrój dachu + płatew (schemat)
# -------------------------
def svg_roof_main(data):
    inp = data["input"]
    res = data["results"]
    p = data["purlin"]

    span = inp["span_cm"]
    angle = inp["angle_deg"]
    eave = inp["eave_out_cm"]
    wallplate_w = inp["wallplate_w_cm"]
    wallplate_h = inp["wallplate_h_cm"]
    rafter_h = inp["rafter_h_cm"]

    half = res["polowa_rozpietosci_cm"]
    rise = res["wysokosc_kalenicy_nad_gora_murlaty_cm"]

    W, H = 980, 460
    pad = 60

    left_outer = (0, 0)
    right_outer = (span, 0)
    ridge = (half, rise)

    left_eave = (-eave, 0)
    right_eave = (span + eave, 0)

    max_x = span + 2 * eave
    max_y = max(rise, 1)
    s = min((W - 2 * pad) / max_x, (H - 2 * pad) / max_y)

    def tx(x): return pad + (x + eave) * s
    def ty(y): return H - pad - y * s

    thick_px = clamp((rafter_h * s) * 0.20, 6, 18)

    def line(p1, p2, stroke="#111", width=3, dash=None):
        ds = f' stroke-dasharray="{dash}"' if dash else ""
        return f'<line x1="{tx(p1[0])}" y1="{ty(p1[1])}" x2="{tx(p2[0])}" y2="{ty(p2[1])}" stroke="{stroke}" stroke-width="{width}"{ds} />'

    def text(x, y, t, size=14, color="#111", anchor="start"):
        return f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-family="Arial" text-anchor="{anchor}">{t}</text>'

    def poly(points, stroke="#111", width=2, fill="none"):
        pts = " ".join([f"{tx(x)},{ty(y)}" for x, y in points])
        return f'<polyline points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="{width}" />'

    svg = [f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">']
    svg.append('<rect width="100%" height="100%" fill="#ffffff"/>')
    svg.append(text(20, 30, "Rysunek 1: przekrój dachu (cm)", 18))
    svg.append(text(20, 54, f"Rozpiętość: {fmt_cm(span)} | kąt: {fmt_deg(angle)} | okap: {fmt_cm(eave)}", 13, "#444"))

    # murłaty (realna wys. z pola)
    left_wp = [(0, -wallplate_h), (wallplate_w, -wallplate_h), (wallplate_w, 0), (0, 0), (0, -wallplate_h)]
    right_wp = [(span - wallplate_w, -wallplate_h), (span, -wallplate_h), (span, 0), (span - wallplate_w, 0), (span - wallplate_w, -wallplate_h)]
    svg.append(poly(left_wp, stroke="#777", width=2))
    svg.append(poly(right_wp, stroke="#777", width=2))
    svg.append(text(tx(wallplate_w/2), ty(-wallplate_h-2), "murłata", 12, "#777", anchor="middle"))

    # krokwie
    svg.append(line(left_eave, ridge, stroke="#111", width=thick_px))
    svg.append(line(ridge, right_eave, stroke="#111", width=thick_px))
    svg.append(line(left_outer, right_outer, stroke="#444", width=2))

    # płatew (góra)
    if p:
        y = p["y_top_cm"]
        x = p["x_cm"]
        p1 = (x, y)
        p2 = (span - x, y)
        svg.append(line(p1, p2, stroke="#0b6", width=5))
        svg.append(text(tx(p1[0]), ty(p1[1]) - 10, "góra płatwi", 12, "#0b6"))
        svg.append(line((p1[0], 0), (p1[0], p1[1]), stroke="#0b6", width=3, dash="3,6"))

    svg.append('</svg>')
    return "\n".join(svg)

# -------------------------
# SVG 2: detal PRO - siodło na murłacie + siodło na płatwi
# -------------------------
def svg_detail_notches(data):
    inp = data["input"]
    res = data["results"]
    p = data["purlin"]

    angle = inp["angle_deg"]
    rafter_h = inp["rafter_h_cm"]
    bearing = inp["bearing_cm"]

    m_depth = res["murlata_siodlo_w_dol_cm"]
    m_horiz = res["murlata_siodlo_poziomo_cm"]

    # purlin notch (może być None)
    p_depth = p["notch_depth_cm"] if p else None
    p_horiz = p["notch_horiz_cm"] if p else None
    p_h = inp["purlin_section_h_cm"] if p else None

    W, H = 980, 460
    pad = 60

    # skala pod detal
    max_x = 240
    max_y = 140
    s = min((W - 2*pad)/max_x, (H - 2*pad)/max_y)

    def tx(x): return pad + x*s
    def ty(y): return H - pad - y*s

    def line_xy(x1,y1,x2,y2, stroke="#111", width=3, dash=None):
        ds = f' stroke-dasharray="{dash}"' if dash else ""
        return f'<line x1="{tx(x1)}" y1="{ty(y1)}" x2="{tx(x2)}" y2="{ty(y2)}" stroke="{stroke}" stroke-width="{width}"{ds} />'

    def text(x, y, t, size=14, color="#111", anchor="start"):
        return f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-family="Arial" text-anchor="{anchor}">{t}</text>'

    def poly(points, stroke="#111", width=2, fill="none"):
        pts = " ".join([f"{tx(x)},{ty(y)}" for x,y in points])
        return f'<polyline points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="{width}" />'

    svg = [f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">']
    svg.append('<rect width="100%" height="100%" fill="#ffffff"/>')
    svg.append(text(20, 30, "Rysunek 2: detal PRO – siodełka (cm)", 18))
    svg.append(text(20, 54, f"Kąt: {fmt_deg(angle)} | siodełko w dół: {fmt_cm(bearing)} (tak samo na murłacie i płatwi)", 13, "#444"))

    # Rafter rectangle (schemat)
    L = 200
    Hk = rafter_h
    rafter_rect = [(0,0), (L,0), (L,Hk), (0,Hk), (0,0)]
    svg.append(poly(rafter_rect, stroke="#111", width=3))

    # Murłata notch (na dole krokwi, schematycznie z lewej)
    # Pokazujemy "w dół" i "poziomo"
    x0 = 20
    # notch od dołu krokwi w górę? Uproszczenie: pokażemy "wybranie" od dołu do góry o m_depth
    # i po poziomie m_horiz
    notch_m = [
        (x0, 0),
        (x0 + m_horiz, 0),
        (x0 + m_horiz, m_depth),
        (x0, m_depth),
        (x0, 0)
    ]
    svg.append(poly(notch_m, stroke="#c00", width=4))
    svg.append(text(tx(x0), ty(m_depth+8), "siodełko na murłacie", 12, "#c00"))

    # Wymiary murłaty
    svg.append(line_xy(x0 + m_horiz + 10, 0, x0 + m_horiz + 10, m_depth, stroke="#c00", width=2, dash="4,6"))
    svg.append(text(tx(x0 + m_horiz + 18), ty(m_depth/2), f"w dół: {fmt_cm(m_depth)}", 12, "#c00"))
    svg.append(line_xy(x0, -8, x0 + m_horiz, -8, stroke="#c00", width=2, dash="4,6"))
    svg.append(text((tx(x0)+tx(x0+m_horiz))/2, ty(-8) - 6, f"poziomo: {fmt_cm(m_horiz)}", 12, "#c00", anchor="middle"))

    # Płatew notch (na górze krokwi, bardziej w prawo)
    if p:
        x1 = 110
        y_top = Hk
        notch_p = [
            (x1, y_top),
            (x1 + p_horiz, y_top),
            (x1 + p_horiz, y_top - p_depth),
            (x1, y_top - p_depth),
            (x1, y_top),
        ]
        svg.append(poly(notch_p, stroke="#0b6", width=4))
        svg.append(text(tx(x1), ty(y_top - p_depth - 8), "siodełko pod płatew", 12, "#0b6"))

        # płatew (prostokąt na siodełku)
        p_rect = [
            (x1, y_top),
            (x1 + p_horiz, y_top),
            (x1 + p_horiz, y_top + p_h),
            (x1, y_top + p_h),
            (x1, y_top),
        ]
        svg.append(poly(p_rect, stroke="#0b6", width=2))

        # wymiary płatwi
        svg.append(line_xy(x1 + p_horiz + 10, y_top, x1 + p_horiz + 10, y_top - p_depth, stroke="#0b6", width=2, dash="4,6"))
        svg.append(text(tx(x1 + p_horiz + 18), ty(y_top - p_depth/2), f"w dół: {fmt_cm(p_depth)}", 12, "#0b6"))
        svg.append(line_xy(x1, y_top - p_depth - 10, x1 + p_horiz, y_top - p_depth - 10, stroke="#0b6", width=2, dash="4,6"))
        svg.append(text((tx(x1)+tx(x1+p_horiz))/2, ty(y_top - p_depth - 10) - 6, f"poziomo: {fmt_cm(p_horiz)}", 12, "#0b6", anchor="middle"))

    svg.append('</svg>')
    return "\n".join(svg)

# -------------------------
# UI
# -------------------------
@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
    <head>
      <meta charset="utf-8"/>
      <meta name="viewport" content="width=device-width, initial-scale=1"/>
      <title>Kalkulator ciesielski – dach dwuspadowy (cm)</title>
      <style>
        body{font-family:Arial;margin:24px;max-width:1100px}
        .grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
        label{display:block;font-size:13px;margin-bottom:4px}
        input{width:100%;padding:10px;border:1px solid #ddd;border-radius:12px}
        .row{margin-bottom:10px}
        .card{border:1px solid #eee;border-radius:16px;padding:16px;box-shadow:0 2px 12px rgba(0,0,0,.05)}
        button{padding:12px 16px;border-radius:12px;border:0;background:#111;color:#fff;font-weight:700;cursor:pointer}
        .muted{color:#666;font-size:13px;line-height:1.35}
        .full{grid-column:1 / -1}
        .pill{display:inline-block;background:#f4f4f4;border-radius:999px;padding:4px 10px;font-size:12px}
      </style>
    </head>
    <body>
      <h2>Kalkulator ciesielski – dach dwuspadowy <span class="pill">cm</span></h2>
      <p class="muted">
        Odniesienia:<br>
        • Poziom: od <b>zewnętrznej krawędzi murłaty</b> do środka.<br>
        • Pion: w górę od <b>górnej krawędzi murłaty</b>.<br>
        • Siodełko: <b>4 cm w dół</b> na murłacie i na płatwi (jednakowo).
      </p>

      <div class="card">
        <form action="/view" method="get">
          <div class="grid">

            <div class="row">
              <label>Rozpiętość (zewn. krawędź murłaty ↔ zewn. krawędź murłaty) [cm]</label>
              <input name="span_cm" value="1000" />
            </div>

            <div class="row">
              <label>Kąt połaci [°]</label>
              <input name="angle_deg" value="35" />
            </div>

            <div class="row">
              <label>Okap – na zewnątrz w poziomie [cm]</label>
              <input name="eave_out_cm" value="50" />
            </div>

            <div class="row">
              <label>Murłata – szerokość [cm]</label>
              <input name="wallplate_w_cm" value="14" />
            </div>

            <div class="row">
              <label>Murłata – wysokość (żeby liczyć od dołu) [cm]</label>
              <input name="wallplate_h_cm" value="14" />
            </div>

            <div class="row">
              <label>Krokiew – wysokość w przekroju [cm]</label>
              <input name="rafter_h_cm" value="20" />
            </div>

            <div class="row">
              <label>Siodełko (murłata i płatew) – w dół [cm]</label>
              <input name="bearing_cm" value="4" />
            </div>

            <div class="row">
              <label>Płatew – włącz (1=tak, 0=nie)</label>
              <input name="purlin_enabled" value="1" />
            </div>

            <div class="row">
              <label>Płatew – wysokość przekroju [cm] (np. 20)</label>
              <input name="purlin_section_h_cm" value="20" />
            </div>

            <div class="row">
              <label>Płatew – odległość po krokwi od zewn. krawędzi murłaty [cm] (opcjonalnie)</label>
              <input name="purlin_s_from_outer_wallplate_cm" value="0" />
            </div>

            <div class="row">
              <label>Płatew – wysokość GÓRY płatwi nad górą murłaty [cm] (gdy powyżej = 0)</label>
              <input name="purlin_top_above_wallplate_cm" value="120" />
            </div>

            <div class="row full">
              <div class="muted">
                Jeśli podasz <b>odległość po krokwi</b>, ona ma priorytet.<br>
                Jeśli zostawisz 0, użyjemy <b>wysokości GÓRY płatwi</b>.
              </div>
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
def api_calc(
    span_cm: float = 1000,
    angle_deg: float = 35,
    eave_out_cm: float = 50,

    rafter_h_cm: float = 20,
    wallplate_w_cm: float = 14,
    wallplate_h_cm: float = 14,

    bearing_cm: float = 4,

    purlin_enabled: int = 0,
    purlin_section_h_cm: float = 20,
    purlin_s_from_outer_wallplate_cm: float = 0,
    purlin_top_above_wallplate_cm: float = 0,
):
    return calc_roof_cm(
        span_cm, angle_deg, eave_out_cm,
        rafter_h_cm, wallplate_w_cm, wallplate_h_cm,
        bearing_cm,
        bool(purlin_enabled),
        purlin_section_h_cm,
        purlin_s_from_outer_wallplate_cm,
        purlin_top_above_wallplate_cm,
    )

@app.get("/view", response_class=HTMLResponse)
def view(
    span_cm: float = 1000,
    angle_deg: float = 35,
    eave_out_cm: float = 50,

    rafter_h_cm: float = 20,
    wallplate_w_cm: float = 14,
    wallplate_h_cm: float = 14,

    bearing_cm: float = 4,

    purlin_enabled: int = 0,
    purlin_section_h_cm: float = 20,
    purlin_s_from_outer_wallplate_cm: float = 0,
    purlin_top_above_wallplate_cm: float = 0,
):
    data = calc_roof_cm(
        span_cm, angle_deg, eave_out_cm,
        rafter_h_cm, wallplate_w_cm, wallplate_h_cm,
        bearing_cm,
        bool(purlin_enabled),
        purlin_section_h_cm,
        purlin_s_from_outer_wallplate_cm,
        purlin_top_above_wallplate_cm,
    )

    res = data["results"]
    p = data["purlin"]

    svg1 = svg_roof_main(data)
    svg2 = svg_detail_notches(data)

    purlin_html = ""
    if p:
        purlin_html = f"""
        <div class="card">
          <h3>Płatew – pozycja i osadzenie</h3>
          <ul>
            <li>Pozycja płatwi: <b>{fmt_cm(p['x_cm'])}</b> od zewn. krawędzi murłaty (w stronę środka)</li>
            <li>Góra płatwi: <b>{fmt_cm(p['y_top_cm'])}</b> w górę od górnej krawędzi murłaty</li>
            <li>Dół płatwi: <b>{fmt_cm(p['y_bottom_cm'])}</b> w górę od górnej krawędzi murłaty</li>
            <li><b>Dół płatwi od dołu murłaty (pod wieniec/poduszkę): {fmt_cm(p['bottom_from_bottom_wallplate_cm'])}</b></li>
          </ul>
        </div>

        <div class="card">
          <h3>Siodełko pod płatew – do wycięcia w krokwi (tak samo jak na murłacie)</h3>
          <ul>
            <li>W dół: <b>{fmt_cm(p['notch_depth_cm'])}</b></li>
            <li>Poziomo: <b>{fmt_cm(p['notch_horiz_cm'])}</b></li>
            <li>Po krokwi: <b>{fmt_cm(p['notch_along_rafter_cm'])}</b></li>
          </ul>
        </div>
        """

    return f"""
    <html>
    <head>
      <meta charset="utf-8"/>
      <meta name="viewport" content="width=device-width, initial-scale=1"/>
      <title>Wyniki – dach dwuspadowy (cm)</title>
      <style>
        body{{font-family:Arial;margin:24px;max-width:1200px}}
        .grid{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}
        .card{{border:1px solid #eee;border-radius:16px;padding:16px;box-shadow:0 2px 12px rgba(0,0,0,.05)}}
        table{{width:100%;border-collapse:collapse}}
        td{{padding:10px;border-bottom:1px solid #f0f0f0;vertical-align:top}}
        .muted{{color:#666;font-size:13px;line-height:1.35}}
        a{{color:#111}}
        .btn{{display:inline-block;padding:10px 14px;border-radius:12px;background:#111;color:#fff;text-decoration:none;font-weight:700}}
      </style>
    </head>
    <body>
      <a class="btn" href="/">← Zmień dane</a>
      <h2>Wyniki – dach dwuspadowy (cm)</h2>
      <p class="muted">
        Siodełko: <b>{fmt_cm(bearing_cm)}</b> w dół – jednakowo na murłacie i płatwi.
      </p>

      <div class="grid">
        <div class="card">
          <h3>Wymiary i kąty</h3>
          <table>
            <tr><td>Połowa rozpiętości</td><td><b>{fmt_cm(res['polowa_rozpietosci_cm'])}</b></td></tr>
            <tr><td>Wysokość kalenicy nad górą murłaty</td><td><b>{fmt_cm(res['wysokosc_kalenicy_nad_gora_murlaty_cm'])}</b></td></tr>
            <tr><td>Długość krokwi po osi (bez okapu)</td><td><b>{fmt_cm(res['dlugosc_krokwi_po_osi_bez_okapu_cm'])}</b></td></tr>
            <tr><td>Długość krokwi po osi (z okapem)</td><td><b>{fmt_cm(res['dlugosc_krokwi_po_osi_z_okapem_cm'])}</b></td></tr>
            <tr><td>Kąt cięcia przy kalenicy (plumb)</td><td><b>{fmt_deg(res['kat_plumb_kalenica_deg'])}</b></td></tr>
            <tr><td>Kąt cięcia przy murłacie (seat)</td><td><b>{fmt_deg(res['kat_seat_murlata_deg'])}</b></td></tr>
          </table>
        </div>

        <div class="card">
          <h3>Siodełko na murłacie</h3>
          <table>
            <tr><td>W dół</td><td><b>{fmt_cm(res['murlata_siodlo_w_dol_cm'])}</b></td></tr>
            <tr><td>Poziomo</td><td><b>{fmt_cm(res['murlata_siodlo_poziomo_cm'])}</b></td></tr>
            <tr><td>Po krokwi</td><td><b>{fmt_cm(res['murlata_siodlo_po_krokwi_cm'])}</b></td></tr>
          </table>
        </div>

        <div class="card" style="grid-column:1 / -1;">
          <h3>Rysunek 1</h3>
          {svg1}
        </div>

        <div class="card" style="grid-column:1 / -1;">
          <h3>Rysunek 2 – detal PRO</h3>
          {svg2}
        </div>

        {purlin_html}

        <div class="card" style="grid-column:1 / -1;">
          <h3>API (JSON)</h3>
          <div class="muted">Te same dane w JSON:</div>
          <div><a href="/api/calc?span_cm={span_cm}&angle_deg={angle_deg}&eave_out_cm={eave_out_cm}&rafter_h_cm={rafter_h_cm}&wallplate_w_cm={wallplate_w_cm}&wallplate_h_cm={wallplate_h_cm}&bearing_cm={bearing_cm}&purlin_enabled={purlin_enabled}&purlin_section_h_cm={purlin_section_h_cm}&purlin_s_from_outer_wallplate_cm={purlin_s_from_outer_wallplate_cm}&purlin_top_above_wallplate_cm={purlin_top_above_wallplate_cm}">/api/calc (link)</a></div>
        </div>
      </div>
    </body>
    </html>
    """
