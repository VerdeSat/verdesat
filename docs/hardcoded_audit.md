


# Hardcoded Parameter Audit

| Variable/Magic String    | File:Line (example)                                          | What it Controls                      | Quick-Fix         | Param/Config Name     | Critical? |
|--------------------------|-------------------------------------------------------------|---------------------------------------|-------------------|----------------------|-----------|
| "NDVI"                   | ingestion/chips.py:230,231,235,319,334<br>core/cli.py:241,243,696,728<br>ingestion/indices.py:7<br>analytics/timeseries.py:19<br>templates/report.html.j2:22-65 | Index name, band selection, reporting | param/config      | index                | YES       |
| "mean_ndvi"              | core/cli.py:349,350,381,382,442,481,482,773<br>analytics/trend.py:7<br>analytics/preprocessing.py:9<br>analytics/stats.py:35-38,88<br>analytics/decomposition.py:20<br>analytics/timeseries.py:50,75,85,92,93 | Output column name                    | param/config      | value_col            | YES       |
| "EVI"                    | ingestion/indices.py:26,29,36,38,42,45,47,50<br>core/cli.py:84,308,324,331,332,334 | Additional index                      | param/config      | index                | YES       |
| "B4", "B5"               | ingestion/indices.py:7,18,19<br>ingestion/chips.py:303<br>core/cli.py:253 | Sensor band mapping                   | sensor config     | red_band, nir_band   | YES       |
| "NASA/HLS/HLSL30/v002"   | core/cli.py:74,134                                          | Default satellite collection          | param/config      | collection           | YES       |
| "30"                     | ingestion/chips.py:286<br>core/cli.py:79,153<br>analytics/timeseries.py:14,46 | Spatial resolution (meters)           | param/config      | scale                | YES       |
| "fmask"                  | ingestion/mask.py:18,19                                     | Cloud mask strategy                   | strategy/config   | mask_method          | YES       |
| "chips/"                 | core/cli.py:207                                             | Output directory for chips            | param/config      | chips_dir            | YES       |
| "gifs/"                  | core/cli.py:530                                             | Output directory for GIFs             | param/config      | gifs_dir             | YES       |
| "output/"                | core/cli.py:692                                             | Output folder for results             | param/config      | output_dir           | YES       |
| "verdesat_output"        | core/cli.py:692                                             | Output folder for reports             | param/config      | output_dir           | YES       |
| "ee.Reducer.mean()"      | ingestion/chips.py,<br>analytics/stats.py (and others?)     | Composite reducer function            | param/config      | reducer              | YES       |
| "period=12"              | analytics/decomposition.py,<br>core/cli.py (and others?)    | Decomposition seasonal period         | param/config/auto | period               | YES       |
| mask_clouds: True        | ingestion/downloader.py:74                                  | Cloud mask default                    | param/config      | mask_clouds          | YES       |
| 0.0, 1.0, 0.4            | ingestion/chips.py:335,337,338,339                          | Palette min/max stretch               | param/config      | stretch_min/max      | MAYBE     |
| "default" font           | visualization/animate.py:40,42,43,48,113,115,116,121        | Default font for GIFs                 | param/config      | font, font_size      | NO        |
| "arial.ttf"              | visualization/animate.py:46,119                             | Font for text overlay                 | param/config      | font                 | NO        |
| "id", "system:index"     | ingestion/chips.py:127,389<br>ingestion/shapefile_preprocessor.py:100 | Feature IDs                  | param/config      | id_col                | MAYBE     |
| Date/time defaults       | core/cli.py:77,78,137,138                                   | Start/end dates                       | param/config      | start_date, end_date | NO        |
| Frequency defaults       | core/cli.py:91,143,314,488<br>analytics/timeseries.py:85    | Aggregation frequency                 | param/config      | freq                 | NO        |
| Output CSV/PNG names     | core/cli.py:98,321,359,398,430,448,500,524,578,642          | Output file naming                    | param/config      | output_file          | MAYBE     |
| "VerdeSat Report"        | core/cli.py:636,694                                         | Report title                          | param/config      | report_title         | NO        |

---

### Critical (must modularize/parameterize in Sprint 1):
- Index name (“NDVI”, “EVI”, etc)
- Output column (“mean_ndvi”, etc)
- Band mapping (“B4”, “B5”)
- Collection (“NASA/HLS/HLSL30/v002”)
- Scale (30)
- Cloud mask/fmask
- Composite reducer
- Decomposition period
- Output directories (“chips/”, “gifs/”, “output/”)
- mask_clouds

### Nice-to-fix:
- Palette min/max, font, report title, date/freq defaults, output file names, id columns.