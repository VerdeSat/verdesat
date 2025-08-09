

# PDF Reporting Templates (Jinja2 + HTML/CSS)

This file contains **production-ready HTML/Jinja2 templates** and **print CSS** to generate A4 PDFs for VerdeSat. Render using **WeasyPrint** (preferred) or **wkhtmltopdf**. No new files are required; copy the blocks below into your codebase as needed.

---

## 1) ESRS/TNFD Evidence Pack – `evidence_pack_report.html.j2`

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{{ report_title or "VerdeSat Evidence Pack" }}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    {{ print_css|safe }}
  </style>
</head>
<body>
  <header class="vs-header">
    <div class="brand">VerdeSat</div>
    <div class="meta">
      <div>{{ report_date }}</div>
      <div>AOI: {{ aoi_name }} ({{ aoi_id }})</div>
      <div>Method v{{ method_version }} • Hash {{ report_hash[:8] if report_hash else '' }}</div>
    </div>
  </header>

  <main>
    <!-- HERO / EXEC SUMMARY -->
    <section class="hero">
      <h1>Biodiversity & Forest‑Health Screening</h1>
      <p class="subhead">CSRD/TNFD‑friendly indicators. Screening‑grade; best for forests. Not a species inventory.</p>
      <div class="summary-grid">
        <div class="panel">
          <div class="kpi-label">B‑Score</div>
          <div class="bscore">{{ bscore|round(0) if bscore is not none else '–' }}/100</div>
          <div class="band {{ bscore_band|lower }}">{{ bscore_band_label }}</div>
          <div class="kpi-note">Weights: I {{ weights.intactness }} / S {{ weights.shannon }} / F {{ weights.fragmentation }}</div>
        </div>
        <figure class="map">
          <img src="{{ map_png }}" alt="AOI map with overlay" />
          <figcaption>AOI boundary and latest composite ({{ acquisition_from }} → {{ acquisition_to }})</figcaption>
        </figure>
        <div class="kpi-strip">
          <div class="kpi"><span>Intactness</span><strong>{{ intactness_pct|round(1) }}%</strong></div>
          <div class="kpi"><span>Frag‑Norm</span><strong>{{ frag_norm|round(2) }}</strong></div>
          <div class="kpi"><span>NDVI μ</span><strong>{{ ndvi_mean|round(3) }}</strong></div>
          <div class="kpi"><span>NDVI slope/yr</span><strong>{{ ndvi_slope|round(3) }}</strong></div>
          <div class="kpi"><span>ΔNDVI YoY</span><strong>{{ ndvi_delta|round(3) }}</strong></div>
          <div class="kpi"><span>% valid obs</span><strong>{{ valid_obs_pct|round(0) }}%</strong></div>
        </div>
      </div>
      <p class="executive">{{ executive_summary }}</p>
    </section>

    <!-- PROTECTED AREAS / SENSITIVITY -->
    <section>
      <h2>Context: Protected & Sensitive Areas</h2>
      <table class="simple">
        <thead><tr><th>Inside PA?</th><th>Nearest PA</th><th>Distance</th><th>Nearest KBA</th><th>Distance</th></tr></thead>
        <tbody>
          <tr>
            <td>{{ inside_pa|default(false) and 'Yes' or 'No' }}</td>
            <td>{{ nearest_pa_name or '–' }}</td>
            <td>{{ nearest_pa_distance_km is not none and (nearest_pa_distance_km|round(2) ~ ' km') or '–' }}</td>
            <td>{{ nearest_kba_name or '–' }}</td>
            <td>{{ nearest_kba_distance_km is not none and (nearest_kba_distance_km|round(2) ~ ' km') or '–' }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <!-- TRENDS -->
    <section>
      <h2>Vegetation Trends</h2>
      <figure>
        <img src="{{ timeseries_png }}" alt="NDVI/MSAVI time series and trend" />
        <figcaption>Smoothed NDVI/MSAVI with seasonal decomposition and linear trend.</figcaption>
      </figure>
    </section>

    <!-- ESRS E4 MAPPING -->
    <section>
      <h2>ESRS E4 Mapping (screening)</h2>
      <table class="kv">
        <tr><th>Extent & Condition</th><td>{{ esrs_extent_condition }}</td></tr>
        <tr><th>Pressures</th><td>{{ esrs_pressures }}</td></tr>
        <tr><th>Targets</th><td>{{ esrs_targets }}</td></tr>
        <tr><th>Actions & Resources</th><td>{{ esrs_actions }}</td></tr>
        <tr><th>Anticipated Financial Effects</th><td>{{ esrs_financial_effects }}</td></tr>
      </table>
      <p class="disclaimer">Screening‑grade outputs. Field validation recommended for regulatory sign‑off.</p>
    </section>

    <!-- DATA & METHODS -->
    <section>
      <h2>Methods & Limitations</h2>
      <ul class="bullets">
        <li>AOI aggregation to handle mixed resolutions (10 m ↔ 300 m); report pixel counts and % valid observations.</li>
        <li>MSA 2015 (300 m) used as pressure context; vintage and coarseness disclosed.</li>
        <li>NDVI saturation in dense canopies considered in interpretation; seasonal decomposition applied.</li>
      </ul>
      <p>{{ methods_text }}</p>
      <h3>Data lineage</h3>
      <pre class="code">{{ lineage_json|tojson(indent=2) }}</pre>
      <h3>Sources</h3>
      <table class="simple">
        <thead><tr><th>Name</th><th>Version</th><th>Date Range</th><th>Resolution</th><th>Notes</th></tr></thead>
        <tbody>
          {% for s in sources %}
          <tr>
            <td>{{ s.name }}</td>
            <td>{{ s.version }}</td>
            <td>{{ s.date_range }}</td>
            <td>{{ s.resolution }}</td>
            <td>{{ s.notes }}</td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </section>
  </main>

  <footer class="vs-footer">
    <div>© {{ year }} VerdeSat • Data: Sentinel‑2, Esri LULC 10 m, GLOBIO MSA 2015 (300 m), EFA/EFT 300 m (where available), WDPA/KBA</div>
    <div class="page-num">Page <span class="pageNumber"></span> / <span class="totalPages"></span></div>
  </footer>
</body>
</html>
```

---

## 2) EUDR Helper Pack – `eudr_report.html.j2`

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{{ report_title or "VerdeSat EUDR Pack" }}</title>
  <style>
    {{ print_css|safe }}
  </style>
</head>
<body>
  <header class="vs-header">
    <div class="brand">VerdeSat</div>
    <div class="meta">
      <div>{{ report_date }}</div>
      <div>Batch: {{ batch_id }}</div>
      <div>Method v{{ method_version }} • Hash {{ report_hash[:8] if report_hash else '' }}</div>
    </div>
  </header>
  <main>
    <h1>EUDR Due Diligence — Geolocation & Deforestation Check</h1>
    <p class="disclaimer">Summary to assist Article 9 information collection and deforestation‑since‑2020 checks. Legal compliance and DDS submission remain operator responsibility.</p>

    <section>
      <h2>Polygons & Precision</h2>
      <table class="simple">
        <thead><tr><th>Plot ID</th><th>Area (ha)</th><th>Geometry</th><th>Precision</th><th>Notes</th></tr></thead>
        <tbody>
          {% for p in plots %}
          <tr>
            <td>{{ p.id }}</td>
            <td>{{ p.area_ha|round(2) }}</td>
            <td>{{ p.geom_type }}</td>
            <td>{{ p.precision_decimals }} dp</td>
            <td>{{ p.notes or '' }}</td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </section>

    <section>
      <h2>Deforestation Since 2021</h2>
      <table class="simple">
        <thead><tr><th>Plot ID</th><th>Loss 2021+</th><th>Area (ha)</th><th>Alerts (GLAD/RADD)</th><th>Evidence</th></tr></thead>
        <tbody>
          {% for r in deforestation_rows %}
          <tr>
            <td>{{ r.id }}</td>
            <td>{{ r.loss_flag and 'Yes' or 'No' }}</td>
            <td>{{ r.loss_area_ha|round(2) }}</td>
            <td>{{ r.alerts or 0 }}</td>
            <td><a href="{{ r.snapshot_png }}">map</a></td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
      <p class="foot">Loss layers: GFC v{{ gfc_version }}, alerts: {{ alert_sources }}.</p>
    </section>

    <section>
      <h2>DDS Manifest (export)</h2>
      <pre class="code">{{ dds_manifest_csv }}</pre>
      <p class="foot">Keep records for 5 years. Submit via EU EUDR Information System.</p>
    </section>

    <section>
      <h2>Lineage</h2>
      <pre class="code">{{ lineage_json|tojson(indent=2) }}</pre>
    </section>
  </main>
  <footer class="vs-footer">
    <div>© {{ year }} VerdeSat • Data: Sentinel‑2, Landsat, GFC loss, GLAD/RADD, admin/basemaps</div>
    <div class="page-num">Page <span class="pageNumber"></span> / <span class="totalPages"></span></div>
  </footer>
</body>
</html>
```

---

## 3) Print CSS – `print_css` (embed variable)

```css
@page { size: A4; margin: 18mm 16mm; }
body { font: 11.5pt/1.45 "Inter", Arial, sans-serif; color: #0f172a; }

.vs-header, .vs-footer { display: flex; justify-content: space-between; align-items: center; font-size: 9.5pt; color: #475569; }
.vs-header { border-bottom: 1px solid #e2e8f0; padding-bottom: 6px; margin-bottom: 12px; }
.vs-footer { border-top: 1px solid #e2e8f0; padding-top: 6px; margin-top: 12px; }
.vs-header .brand { font-weight: 700; color: #065f46; }

h1 { font-size: 19pt; margin: 8px 0 2px; }
h2 { font-size: 14pt; margin: 14px 0 6px; color: #0b4f3f; }
h3 { font-size: 12pt; margin: 10px 0 4px; }
.subhead { color: #475569; margin-top: 2px; }
.disclaimer { color: #64748b; font-size: 10pt; }
.foot { color: #64748b; font-size: 9.5pt; }

.summary-grid { display: grid; grid-template-columns: 1.1fr 1.5fr; grid-template-rows: auto auto; gap: 10px; margin-top: 8px; }
.summary-grid .panel { border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px; }
.summary-grid .map img { width: 100%; border-radius: 8px; border: 1px solid #e2e8f0; }
.kpi-strip { display: grid; grid-template-columns: repeat(6, 1fr); gap: 6px; }
.kpi { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 6px 8px; font-size: 10.5pt; }
.kpi span { color: #475569; display: block; font-size: 9.5pt; }

.bscore { font-size: 26pt; font-weight: 800; color: #0b4f3f; }
.band { font-size: 10.5pt; margin-top: 4px; display: inline-block; padding: 2px 6px; border-radius: 5px; }
.band.low { background: #dcfce7; color: #166534; }
.band.moderate { background: #fef9c3; color: #92400e; }
.band.high { background: #fee2e2; color: #991b1b; }

.simple { width: 100%; border-collapse: collapse; font-size: 10.5pt; }
.simple th, .simple td { border: 1px solid #e2e8f0; padding: 6px 8px; text-align: left; }
.simple thead th { background: #f1f5f9; }

.kv { width: 100%; border-collapse: collapse; }
.kv th { width: 34%; vertical-align: top; text-align: left; color: #334155; }
.kv td, .kv th { border-top: 1px solid #e2e8f0; padding: 6px 8px; }

.bullets { margin: 0; padding-left: 18px; }
.code { background: #0b1020; color: #e5e7eb; border-radius: 6px; padding: 10px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 9.5pt; white-space: pre-wrap; }

.page-num { }

/* WeasyPrint page counters */
@page { @bottom-right { content: "Page " counter(page) " / " counter(pages); } }
```

---

## 4) Minimal Python to render (WeasyPrint)

```python
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
from datetime import date

# Load templates stored as strings or files
env = Environment(loader=FileSystemLoader("./"))
# If you keep the HTML in a string, wrap with env.from_string(...)
tpl = env.from_string(open("evidence_pack_report.html.j2", "r", encoding="utf-8").read())

context = dict(
    report_title="VerdeSat Evidence Pack",
    report_date=date.today().isoformat(),
    aoi_name="Mexico Restoration AOI 1",
    aoi_id="MX-REST-001",
    method_version="0.2.0",
    report_hash="{{computed_sha256}}",
    bscore=54, bscore_band="Moderate", bscore_band_label="Moderate risk",
    weights=dict(intactness=0.4, shannon=0.3, fragmentation=0.3),
    intactness_pct=62.1, frag_norm=0.44, ndvi_mean=0.72, ndvi_slope=0.012, ndvi_delta=0.021,
    valid_obs_pct=87.0,
    acquisition_from="2024-01-01", acquisition_to="2024-12-31",
    executive_summary="Moderate condition; fragmentation elevated; greenness improving (0.012/yr).",
    inside_pa=False, nearest_pa_name="",
    nearest_pa_distance_km=None, nearest_kba_name="",
    nearest_kba_distance_km=None,
    timeseries_png="timeseries.png", map_png="aoi_map.png",
    esrs_extent_condition="Intactness 62%, Frag‑Norm 0.44; NDVI stable to improving.",
    esrs_pressures="MSA 2015 indicates moderate pressure; EFA seasonal variability normal.",
    esrs_targets="Intactness +5 pp in 24 months; fragmentation −10%.",
    esrs_actions="Native planting, buffer creation, maintenance budget.",
    esrs_financial_effects="Low to moderate; mitigation costs budgeted in OPEX.",
    methods_text="AOI‑level aggregation; mixed resolution handled via summary stats.",
    sources=[
      dict(name="Sentinel‑2 L2A", version="v2024", date_range="2017–present", resolution="10 m", notes="NDVI/MSAVI composites"),
      dict(name="Esri 10 m Land Cover", version="2023", date_range="2020–2023", resolution="10 m", notes="Habitat mask"),
      dict(name="GLOBIO MSA", version="2015", date_range="2015", resolution="300 m", notes="Pressure context (vintage)"),
      dict(name="EFA/EFT", version="current", date_range="rolling", resolution="300 m", notes="Functional attributes (context)")
    ],
    lineage_json={"example": True},
    print_css=open("print.css", "r", encoding="utf-8").read(),
    year=date.today().year,
)

html = tpl.render(**context)
HTML(string=html, base_url=".").write_pdf("report.pdf")
```

---

## 5) Data Sources (for templates)

Use or display the following sources (match what’s available in your pipeline):

- **Sentinel‑2 L2A** (10 m; 2017–present) — NDVI/MSAVI composites, s2cloudless mask
- **Landsat 8/9 SR** (30 m; 2013–present) — optional long‑term context
- **Esri 10 m Land Cover** (2020–2023) — habitat/intactness; fragmentation, Shannon
- **ESA WorldCover 10 m** (2020/2021) — fallback cross‑check
- **GLOBIO MSA 2015** (300 m) — pressure context (already in use)
- **EFA/EFT** (300 m; 10‑day/seasonal) — functional attributes (context)
- **Global Forest Change (Hansen) — Tree cover loss** (annual) — EUDR deforestation since 2021
- **GLAD** (optical alerts) & **RADD** (radar alerts) — optional EUDR support
- **WDPA** (protected areas) & **KBA** (key biodiversity areas) — proximity/sensitivity
- **WWF Terrestrial Ecoregions** — biome/ecoregion labels
- **Natural Earth / GADM** — admin/basemap context
- **GBIF occurrences** — optional screening‑grade validation
- **Human Footprint / Accessibility to Cities** — optional pressure proxies (disclose vintage)

---

### Notes
- Keep **screening‑grade** phrasing; do not position outputs as species‑level counts.
- Always include **vintages, versions, resolution** in the “Sources” table and `lineage.json`.
- For mixed resolutions, report **AOI‑level aggregates** and **valid obs %**.
