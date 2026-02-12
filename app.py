from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import math

app = FastAPI()

# -------------------------
# Helpers
# -------------------------
def clamp(v, a, b):
    return max(a, min(b, v))

def fmt_cm(x):
    return f"{x:.1f} cm"

def fmt_deg(x):
    return f"{x:.2f}°"

# -------------------------
# Core calc (ALL in cm)
# Geometry reference:
# - span_cm: od zewnętrznej krawędzi murłaty lewej do zewnętrznej krawędzi murłaty prawej (w poziomie)
# - angle_deg: kąt połaci do poziomu
# - eave_out_cm: wysunięcie na zewnątrz w poziomie poza zewnętrzną krawędź murłaty
# - ridge_height_cm: wysokość kalenicy względem górnej krawędzi murłaty
# - purlin_h_above_wallplate_cm: wysokość płatwi w górę od górnej krawędzi murłaty
# - purlin_s_from_outer_wallplate_cm: odległość po krokwi od punktu oparcia nad zewnętrzną krawędzią murłaty
# -------------------------
def calc_roof_cm(
    span_cm: float,
    angle_deg: float,
    eave_out_cm: float,
    rafter_h_cm: float,      # wysokość krokwi w przekroju
    wallplate_w_cm: float,   # szerokość murłaty (na "siedzisko" zaciosu)
    purlin_enabled: bool,
    purlin_h_above_wallplate_cm: float,
    purlin_s_from_outer_wallplate_cm: float,
):
    ang = math.radians(angle_deg)
    half_span_cm = span_cm / 2.0

    # wysokość kalenicy nad górną krawędzią murłaty
    ridge_height_cm = half_span_cm * math.tan(ang)

    # długość krokwi po osi (bez okapu / z okapem)
    rafter_len_no_eave_cm = half_span_cm / math.cos(ang)
    rafter_len_with_eave_cm = (half_span_cm + eave_out_cm) / math.cos(ang)

    # kąty cięć (pod piłę)
    # - plumb cut przy kalenicy (pionowe cięcie względem krokwi) ~ kąt połaci
    # - seat cut przy murłacie (prostopadłe do plumb) ~ 90 - kąt połaci
    plumb_cut_deg = angle_deg
    seat_cut_deg = 90.0 - angle_deg

    # Zacios (birdsmouth) — głębokość max 1/3 wysokości krokwi
    bird_depth_cm = 0.33 * rafter_h_cm

    # Długość siedziska wynikająca z głębokości (po poziomie):
    # depth = seat * tan(angle) => seat = depth / tan(angle)
    bird_seat_len_cm = bird_depth_cm / math.tan(ang) if math.tan(ang) != 0 else 0.0

    # Nie przekraczamy szerokości murłaty (żeby nie wyszło absurdalne)
    bird_seat_len_cm = min(bird_seat_len_cm, wallplate_w_cm)

    # Punkt "teoretycznego" oparcia nad zewnętrzną krawędzią murłaty (poziomo 0 od zew. krawędzi)
    # Współrzędne lokalne dla połowy dachu:
    # x=0 na zewnętrznej krawędzi murłaty, x rośnie do środka, y w górę od górnej krawędzi murłaty
    # Kalenica jest w (half_span_cm, ridge_height_cm)

    purlin = None
    if purlin_enabled:
        if purlin_s_from_outer_wallplate_cm and purlin_s_from_outer_wallplate_cm > 0:
            s = clamp(purlin_s_from_outer_wallplate_cm, 0, rafter_len_no_eave_cm)
            x = math.cos(ang) * s
            y = math.sin(ang) * s
            purlin = {"mode": "s", "s_cm": s, "x_cm": x, "y_cm": y}
        else:
            y = clamp(purlin_h_above_wallplate_cm, 0, ridge_height_cm)
            x = y / math.tan(ang) if math.tan(ang) != 0 else 0
            s = x / math.cos(ang) if math.cos(ang) != 0 else 0
            purlin = {"mode": "h", "s_cm": s, "x_cm": x, "y_cm": y}

    return {
        "input": {
            "span_cm": span_cm,
            "angle_deg": angle_deg,
            "eave_out_cm": eave_out_cm,
            "rafter_h_cm": rafter_h_cm,
            "wallplate_w_cm": wallplate_w_cm,
            "purlin_enabled": purlin_enabled,
            "purlin_h_above_wallplate_cm": purlin_h_above_wallplate_cm,
            "purlin_s_from_outer_wallplate_cm": purlin_s_from_outer_wallplate_cm,
        },
        "results": {
            "polowa_rozpietosci_od_zewn_murlaty_cm": half_span_cm,
            "wysokosc_kalenicy_nad_gorna_krawedzia_murlaty_cm": ridge_height_cm,
            "dlugosc_krokwi_po_osi_bez_okapu_cm": rafter_len_no_eave_cm,
            "dlugosc_krokwi_po_osi_z_okapem_cm": rafter_len_with_eave_cm,
            "kat_ciecia_przy_kalenicy_plumb_deg": plumb_cut_deg,
            "kat_ciecia_przy_murlacie_seat_deg": seat_cut_deg,
            "zacios_glebokosc_max_1_3_wysokosci_krokwi_cm": bird_depth_cm,
            "zacios_siedzisko_poziomo_ograniczone_do_szerokosci_murlaty_cm": bird_seat_len_cm,
        },
        "purlin": purlin,
    }

# -------------------------
# SVG Drawing (PRO-ish)
# - show wallplates
# - show rafters with thickness
# - show birdsmouth notch
# - show angle arcs
# - show dimensions (span/half/rise/eave)
# - show purlin + support mark
# -------------------------
def svg_roof_pro(data):
    inp = data["input"]
    res = data["results"]
    purlin = data["purlin"]

    span = inp["span_cm"]
    angle = inp["angle_deg"]
    eave = inp["eave_out_cm"]
    rafter_h = inp["rafter_h_cm"]
    wallplate_w = inp["wallplate_w_cm"]

    half = res["polowa_rozpietosci_od_zewn_murlaty_cm"]
    rise = res["wysokosc_kalenicy_nad_gorna_krawedzia_murlaty_cm"]
    bird_depth = res["zacios_glebokosc_max_1_3_wysokosci_krokwi_cm"]
    bird_seat = res["zacios_siedzisko_poziomo_ograniczone_do_szerokosci_murlaty_cm"]

    ang = math.radians(angle)

    # Canvas
    W, H = 980, 460
    pad = 60

    # Model coordinates:
    # Left outer wallplate edge at x=0, top-of-wallplate y=0
    # Right outer wallplate edge at x=span, y=0
    # Ridge at x=half, y=rise
    left_outer = (0, 0)
    right_outer = (span, 0)
    ridge = (half, rise)

    # Eave points (horizontal outwards)
    left_eave = (-eave, 0)
    right_eave = (span + eave, 0)

    # Scale
    max_x = span + 2 * eave
    max_y = max(rise, 1)
    sx = (W - 2 * pad) / max_x
    sy = (H - 2 * pad) / max_y
    s = min(sx, sy)

    def tx(x): return pad + (x + eave) * s
    def ty(y): return H - pad - y * s

    # Rafter thickness: use rafter_h visually, but clamp so it doesn't explode
    thick_px = clamp((rafter_h * s) * 0.20, 6, 18)  # aesthetic stroke width

    def line(p1, p2, stroke="#111", width=3, dash=None):
        ds = f' stroke-dasharray="{dash}"' if dash else ""
        return f'<line x1="{tx(p1[0])}" y1="{ty(p1[1])}" x2="{tx(p2[0])}" y2="{ty(p2[1])}" stroke="{stroke}" stroke-width="{width}"{ds} />'

    def text(x, y, t, size=14, color="#111", anchor="start"):
        return f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-family="Arial" text-anchor="{anchor}">{t}</text>'

    def arc(cx, cy, r, a1_deg, a2_deg, stroke="#111", width=2):
        # arc in screen coords
        a1 = math.radians(a1_deg)
        a2 = math.radians(a2_deg)
        x1 = cx + r * math.cos(a1)
        y1 = cy + r * math.sin(a1)
        x2 = cx + r * math.cos(a2)
        y2 = cy + r * math.sin(a2)
        large = 1 if abs(a2_deg - a1_deg) > 180 else 0
        sweep = 1
        return f'<path d="M {x1:.1f} {y1:.1f} A {r:.1f} {r:.1f} 0 {large} {sweep} {x2:.1f} {y2:.1f}" fill="none" stroke="{stroke}" stroke-width="{width}" />'

    # Birdsmouth notch (left side) - drawn schematically near left outer wallplate
    # We draw a small "step" along rafter near x=0, y=0.
    # Notch depth = bird_depth, seat = bird_seat.
    notch_a = (0, 0)
    notch_b = (bird_seat, 0)
    notch_c = (bird_seat, bird_depth)
    # point on rafter line at height bird_depth => y = tan(angle)*x => x = y/tan(angle)
    x_on_rafter = (bird_depth / math.tan(ang)) if math.tan(ang) != 0 else 0
    notch_d = (x_on_rafter, bird_depth)

    def poly(points, stroke="#111", width=2, fill="none", opacity=1.0):
        pts = " ".join([f"{tx(x)},{ty(y)}" for x, y in points])
        return f'<polyline points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="{width}" opacity="{opacity}" />'

    svg = [f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">']
    svg.append('<rect width="100%" height="100%" fill="#ffffff"/>')

    # Title
    svg.append(text(20, 30, "Kalkulator ciesielski – dach dwuspadowy (cm) | rysunek PRO", 18))
    svg.append(text(20, 54, f"Rozpiętość (zew. krawędź murłaty ↔ zew. krawędź murłaty): {fmt_cm(span)} | Kąt połaci: {fmt_deg(angle)} | Okap: {fmt_cm(eave)}", 13, "#444"))

    # Wallplates (schematic rectangles)
    wp_h_cm = 14  # tylko wizualnie
    left_wp = [(0, -wp_h_cm), (wallplate_w, -wp_h_cm), (wallplate_w, 0), (0, 0), (0, -wp_h_cm)]
    right_wp = [(span - wallplate_w, -wp_h_cm), (span, -wp_h_cm), (span, 0), (span - wallplate_w, 0), (span - wallplate_w, -wp_h_cm)]
    svg.append(poly(left_wp, stroke="#777", width=2))
    svg.append(poly(right_wp, stroke="#777", width=2))
    svg.append(text(tx(wallplate_w/2), ty(-wp_h_cm-2), "murłata (schemat)", 12, "#777", anchor="middle"))

    # Rafters (thick lines)
    svg.append(line(left_eave, ridge, stroke="#111", width=thick_px))
    svg.append(line(ridge, right_eave, stroke="#111", width=thick_px))

    # Base line (top of wallplates)
    svg.append(line(left_outer, right_outer, stroke="#444", width=2))

    # Birdsmouth notch detail (left)
    svg.append(poly([notch_a, notch_b, notch_c, notch_d], stroke="#c00", width=3))
    svg.append(text(tx(10), ty(10), "zacios (schemat)", 12, "#c00"))

    # Angle arcs
    # Ridge arc: show angle between left rafter and horizontal (for illustration)
    rcx, rcy = tx(ridge[0]), ty(ridge[1])
    svg.append(arc(rcx, rcy, 26, 200, 200 + angle, stroke="#0b6", width=3))
    svg.append(text(rcx + 32, rcy - 8, f"{fmt_deg(angle)}", 12, "#0b6"))

    # Seat arc at left outer wallplate (angle to horizontal)
    scx, scy = tx(0), ty(0)
    svg.append(arc(scx, scy, 26, 360 - angle, 360, stroke="#0b6", width=3))
    svg.append(text(scx + 30, scy - 6, f"{fmt_deg(angle)}", 12, "#0b6"))

    # Dimensions: span
    dim_y = -wp_h_cm - 22
    svg.append(line((0, dim_y), (span, dim_y), stroke="#222", width=2, dash="6,6"))
    svg.append(line((0, dim_y+3), (0, -2), stroke="#222", width=1, dash="3,6"))
    svg.append(line((span, dim_y+3), (span, -2), stroke="#222", width=1, dash="3,6"))
    svg.append(text((tx(0)+tx(span))/2, ty(dim_y) - 6, f"rozpiętość: {fmt_cm(span)} (zewn. krawędzie murłat)", 12, "#222", anchor="middle"))

    # Dimension: rise (ridge height)
    svg.append(line((half, 0), (half, rise), stroke="#222", width=2, dash="6,6"))
    svg.append(text(tx(half)+10, ty(rise/2), f"w górę od górnej krawędzi murłaty: {fmt_cm(rise)}", 12, "#222"))

    # Dimension: eave out
    svg.append(line((0, -6), (-eave, -6), stroke="#222", width=2, dash="6,6"))
    svg.append(text((tx(0)+tx(-eave))/2, ty(-6) - 8, f"okap: {fmt_cm(eave)} na zewnątrz w poziomie", 12, "#222", anchor="middle"))

    # Purlin line + support mark
    if purlin:
        y = purlin["y_cm"]
        x = purlin["x_cm"]
        p1 = (x, y)
        p2 = (span - x, y)
        svg.append(line(p1, p2, stroke="#0b6", width=5))
        svg.append(text(tx(p1[0]), ty(p1[1]) - 10, "płatew", 12, "#0b6"))

        # Support mark (schematic) at left purlin point: small vertical post to wallplate line
        svg.append(line((p1[0], 0), (p1[0], p1[1]), stroke="#0b6", width=3, dash="3,6"))
        svg.append(text(tx(p1[0]) + 8, ty(p1[1]/2), "podpora płatwi (schemat)", 12, "#0b6"))

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
        body{font-family:Arial;margin:24px;max-width:1050px}
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
      <h2>Kalkulator ciesielski – dach dwuspadowy <span class="pill">wszystko w cm</span></h2>
      <p class="muted">
        Definicje:<br>
        • <b>Rozpiętość</b> = od <b>zewnętrznej krawędzi murłaty</b> lewej do <b>zewnętrznej krawędzi murłaty</b> prawej (w poziomie).<br>
        • <b>Okap</b> = ile krokiew wychodzi <b>na zewnątrz w poziomie</b> poza zewnętrzną krawędź murłaty.<br>
        • Wysokości liczymy <b>w górę od górnej krawędzi murłaty</b>.
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
              <label>Krokiew – wysokość w przekroju (np. 20 dla 8×20) [cm]</label>
              <input name="rafter_h_cm" value="20" />
            </div>

            <div class="row">
              <label>Płatew – włącz (1=tak, 0=nie)</label>
              <input name="purlin_enabled" value="1" />
            </div>

            <div class="row">
              <label>Płatew – wysokość w górę od górnej krawędzi murłaty [cm]</label>
              <input name="purlin_h_above_wallplate_cm" value="120" />
            </div>

            <div class="row">
              <label>Płatew – odległość po krokwi od zewn. krawędzi murłaty [cm] (opcjonalnie)</label>
              <input name="purlin_s_from_outer_wallplate_cm" value="0" />
            </div>

            <div class="row full">
              <div class="muted">
                Jeśli podasz <b>odległość po krokwi</b>, to ona ma priorytet.<br>
                Jeśli zostawisz 0, użyjemy <b>wysokości płatwi</b>.
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
    purlin_enabled: int = 0,
    purlin_h_above_wallplate_cm: float = 0,
    purlin_s_from_outer_wallplate_cm: float = 0,
):
    data = calc_roof_cm(
        span_cm=span_cm,
        angle_deg=angle_deg,
        eave_out_cm=eave_out_cm,
        rafter_h_cm=rafter_h_cm,
        wallplate_w_cm=wallplate_w_cm,
        purlin_enabled=bool(purlin_enabled),
        purlin_h_above_wallplate_cm=purlin_h_above_wallplate_cm,
        purlin_s_from_outer_wallplate_cm=purlin_s_from_outer_wallplate_cm,
    )
    return data

@app.get("/view", response_class=HTMLResponse)
def view(
    span_cm: float = 1000,
    angle_deg: float = 35,
    eave_out_cm: float = 50,
    rafter_h_cm: float = 20,
    wallplate_w_cm: float = 14,
    purlin_enabled: int = 0,
    purlin_h_above_wallplate_cm: float = 0,
    purlin_s_from_outer_wallplate_cm: float = 0,
):
    data = calc_roof_cm(
        span_cm=span_cm,
        angle_deg=angle_deg,
        eave_out_cm=eave_out_cm,
        rafter_h_cm=rafter_h_cm,
        wallplate_w_cm=wallplate_w_cm,
        purlin_enabled=bool(purlin_enabled),
        purlin_h_above_wallplate_cm=purlin_h_above_wallplate_cm,
        purlin_s_from_outer_wallplate_cm=purlin_s_from_outer_wallplate_cm,
    )
    res = data["results"]
    purlin = data["purlin"]
    svg = svg_roof_pro(data)

    purlin_html = ""
    if purlin:
        purlin_html = f"""
        <div class="card">
          <h3>Płatew (włączona)</h3>
          <ul>
            <li>Wysokość płatwi: <b>{fmt_cm(purlin['y_cm'])}</b> w górę od górnej krawędzi murłaty</li>
            <li>Odległość w poziomie od zewn. krawędzi murłaty do punktu podparcia: <b>{fmt_cm(purlin['x_cm'])}</b></li>
            <li>Odległość po krokwi od zewn. krawędzi murłaty do punktu podparcia: <b>{fmt_cm(purlin['s_cm'])}</b></li>
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
        body{{font-family:Arial;margin:24px;max-width:1150px}}
        .grid{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}
        .card{{border:1px solid #eee;border-radius:16px;padding:16px;box-shadow:0 2px 12px rgba(0,0,0,.05)}}
        table{{width:100%;border-collapse:collapse}}
        td{{padding:10px;border-bottom:1px solid #f0f0f0;vertical-align:top}}
        .muted{{color:#666;font-size:13px;line-height:1.35}}
        a{{color:#111}}
        .btn{{display:inline-block;padding:10px 14px;border-radius:12px;background:#111;color:#fff;text-decoration:none;font-weight:700}}
        .small{{font-size:12px;color:#666}}
      </style>
    </head>
    <body>
      <a class="btn" href="/">← Zmień dane</a>
      <h2>Wyniki – dach dwuspadowy (cm)</h2>
      <p class="muted">
        Wszystkie odległości liczone od: <b>górnej krawędzi murłaty</b> (pion) oraz <b>zewnętrznej krawędzi murłaty</b> (poziom).
      </p>

      <div class="grid">
        <div class="card">
          <h3>Wymiary i kąty (zrozumiale)</h3>
          <table>
            <tr><td>Połowa rozpiętości (zewn. krawędź murłaty → oś kalenicy)</td><td><b>{fmt_cm(res['polowa_rozpietosci_od_zewn_murlaty_cm'])}</b></td></tr>
            <tr><td>Wysokość kalenicy nad górną krawędzią murłaty</td><td><b>{fmt_cm(res['wysokosc_kalenicy_nad_gorna_krawedzia_murlaty_cm'])}</b></td></tr>
            <tr><td>Długość krokwi po osi (bez okapu)</td><td><b>{fmt_cm(res['dlugosc_krokwi_po_osi_bez_okapu_cm'])}</b></td></tr>
            <tr><td>Długość krokwi po osi (z okapem)</td><td><b>{fmt_cm(res['dlugosc_krokwi_po_osi_z_okapem_cm'])}</b></td></tr>
            <tr><td>Kąt cięcia przy kalenicy (plumb)</td><td><b>{fmt_deg(res['kat_ciecia_przy_kalenicy_plumb_deg'])}</b></td></tr>
            <tr><td>Kąt cięcia przy murłacie (seat)</td><td><b>{fmt_deg(res['kat_ciecia_przy_murlacie_seat_deg'])}</b></td></tr>
          </table>
          <div class="small">Plumb/seat podane jako pomoc do ustawienia piły (wersja geometryczna).</div>
        </div>

        <div class="card">
          <h3>Zacios (birdsmouth)</h3>
          <table>
            <tr><td>Głębokość zaciosu (limit 1/3 wysokości krokwi)</td><td><b>{fmt_cm(res['zacios_glebokosc_max_1_3_wysokosci_krokwi_cm'])}</b></td></tr>
            <tr><td>Długość „siedziska” (poziomo, ograniczona do szerokości murłaty)</td><td><b>{fmt_cm(res['zacios_siedzisko_poziomo_ograniczone_do_szerokosci_murlaty_cm'])}</b></td></tr>
          </table>
          <p class="muted">Na rysunku: zacios zaznaczony na czerwono (schemat).</p>
        </div>

        <div class="card" style="grid-column:1 / -1;">
          <h3>Rysunek (PRO SVG)</h3>
          {svg}
          <p class="muted">Na zielono: kąty + płatew (jeśli włączona). Na czerwono: zacios (schemat).</p>
        </div>

        {purlin_html}

        <div class="card" style="grid-column:1 / -1;">
          <h3>API (JSON)</h3>
          <div class="muted">Te same dane w JSON:</div>
          <div><a href="/api/calc?span_cm={span_cm}&angle_deg={angle_deg}&eave_out_cm={eave_out_cm}&rafter_h_cm={rafter_h_cm}&wallplate_w_cm={wallplate_w_cm}&purlin_enabled={purlin_enabled}&purlin_h_above_wallplate_cm={purlin_h_above_wallplate_cm}&purlin_s_from_outer_wallplate_cm={purlin_s_from_outer_wallplate_cm}">/api/calc (link)</a></div>
        </div>
      </div>
    </body>
    </html>
    """
