"""TerraSense Nigeria — research dashboard.

Run: streamlit run app/streamlit_app.py
Works fully offline once data are fetched + prepared. No LLM key needed.
"""
from __future__ import annotations

import base64
import io
import json
from datetime import date

import folium
import geopandas as gpd
import pandas as pd
import streamlit as st
from folium.plugins import MarkerCluster
from render import overlay
from streamlit_folium import st_folium

from terrasense.assessment.engine import DISCLAIMER, OutsideNigeria, assess
from terrasense.config import load_registry
from terrasense.geo.boundary import BoundaryUnavailable
from terrasense.geo.layers import RASTER_LAYERS, current_dir

st.set_page_config(page_title="TerraSense Nigeria", layout="wide")

STATE_BADGE = {
    "observed_environmental_hazard": ("🟥", "Observed environmental hazard (historical)"),
    "insufficient_evidence": ("⬜", "Insufficient evidence — abstained"),
    "preliminary_requires_expert_review": ("🟨", "Preliminary — requires expert review"),
    "not_assessed": ("▫️", "Not assessed"),
}

st.title("TerraSense Nigeria")
st.caption("Research prototype · Nigeria only · secondary data · " + DISCLAIMER)

if not current_dir().exists():
    st.error("No processed data found. Run `python -I scripts/fetch.py`, `python -I scripts/extract.py` and "
             "`python -I scripts/prepare.py` first (see README).")
    st.stop()

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("Location")
    lat = st.number_input("Latitude", value=st.session_state.get("lat", 12.4093), format="%.5f", min_value=-90.0, max_value=90.0)
    lon = st.number_input("Longitude", value=st.session_state.get("lon", 10.0458), format="%.5f", min_value=-180.0, max_value=180.0)
    use_date = st.checkbox("Specify a date of interest", value=False)
    qdate = st.date_input("Date", value=date(2022, 9, 20), max_value=date.today()) if use_date else None
    st.caption("Click the map to set the location. Presets:")
    presets = {"Hadejia (2022 flood area)": (12.4093, 10.0458), "Lagos mainland": (6.60, 3.35),
               "Abeokuta, Ogun": (7.15, 3.35), "Abuja": (9.08, 7.40)}
    for name, (a, b) in presets.items():
        if st.button(name, width="stretch"):
            st.session_state.lat, st.session_state.lon = a, b
            st.rerun()
    st.header("Map layers")
    show = {l.id: st.checkbox(l.title, value=l.id in ("hadejia_flood_extent_2022", "eo4forest_landcover_2023-12"))
            for l in RASTER_LAYERS}
    show_basins = st.checkbox("HydroBASINS level 6 (drainage basins — not wetlands)", value=False)
    show_s4a = st.checkbox("Soils4Africa field sites (2022–23)", value=False)
    show_gcp = st.checkbox("Wetland study control points", value=False)
    photo = st.file_uploader("Optional site photo (not analysed)", type=["jpg", "jpeg", "png"])

# ---------------------------------------------------------------- map
D = current_dir()
m = folium.Map(location=[lat, lon], zoom_start=7 if (lat, lon) == (9.08, 7.40) else 9, tiles="OpenStreetMap",
               control_scale=True)
folium.GeoJson(json.loads((D / "nga_adm1_display.geojson").read_text()), name="Nigeria states (geoBoundaries/GRID3)",
               style_function=lambda f: {"color": "#555", "weight": 1, "fillOpacity": 0},
               tooltip=folium.GeoJsonTooltip(["shapeName"], aliases=["State"])).add_to(m)
folium.GeoJson(json.loads((D / "coverage_outlines.geojson").read_text()), name="Layer coverage outlines",
               style_function=lambda f: {"color": "#d95f02", "weight": 2, "dashArray": "6 4", "fillOpacity": 0},
               tooltip=folium.GeoJsonTooltip(["layer"])).add_to(m)
for lid, on in show.items():
    if on and (ov := overlay(lid)):
        png, bounds = ov
        folium.raster_layers.ImageOverlay("data:image/png;base64," + base64.b64encode(png).decode(), bounds=bounds,
                                          name=lid, mercator_project=False, opacity=0.8).add_to(m)
if show_basins:
    g = gpd.read_parquet(D / "hybas_lev06_nga.parquet")[["HYBAS_ID", "PFAF_ID", "SUB_AREA", "geometry"]]
    g["geometry"] = g.geometry.simplify(0.01)
    folium.GeoJson(g.to_json(), name="HydroBASINS L6", style_function=lambda f: {"color": "#1f78b4", "weight": 1, "fillOpacity": 0.03},
                   tooltip=folium.GeoJsonTooltip(["HYBAS_ID", "PFAF_ID", "SUB_AREA"])).add_to(m)
if show_s4a:
    g = gpd.read_parquet(D / "s4a_field_nga.parquet")
    mc = MarkerCluster(name="Soils4Africa sites").add_to(m)
    for _, r in g.iterrows():
        folium.CircleMarker([r.latitude, r.longitude], radius=3, color="#6a3d9a",
                            tooltip=f"{r.plot_code} · {r.survey_date.date()} · {r.main_land_use}").add_to(mc)
if show_gcp:
    g = gpd.read_parquet(D / "wetland_gcp_south_ng.parquet")
    g = g[g.qc_reject_reason == ""]
    for _, r in g.iterrows():
        folium.CircleMarker([r.lat, r.lon], radius=3, color="#33a02c", tooltip=r.class_name).add_to(m)
folium.Marker([lat, lon], tooltip="Selected location").add_to(m)
folium.LayerControl(collapsed=False).add_to(m)

col_map, col_panel = st.columns([3, 2])
with col_map:
    out = st_folium(m, height=620, use_container_width=True, returned_objects=["last_clicked"])
    if out and out.get("last_clicked"):
        c = out["last_clicked"]
        if (round(c["lat"], 5), round(c["lng"], 5)) != (round(lat, 5), round(lon, 5)):
            st.session_state.lat, st.session_state.lon = round(c["lat"], 5), round(c["lng"], 5)
            st.rerun()
    st.caption("Map overlays are display renderings; panel values are read from native-resolution rasters. "
               "All layers are HISTORICAL. Orange dashed outlines = where local layers exist.")

# ---------------------------------------------------------------- assessment
with col_panel:
    image_meta = {"filename": photo.name, "content_type": photo.type, "bytes": photo.size, "analysed": False} if photo else None
    try:
        with st.spinner("Looking up evidence…"):
            res = assess(lat, lon, qdate, image_meta)
    except OutsideNigeria as e:
        st.error(str(e))
        st.stop()
    except BoundaryUnavailable as e:
        st.error(str(e))
        st.stop()

    st.subheader(f"{lat:.5f}, {lon:.5f} · {res['query']['admin1'] or 'state unknown'}")
    badge = {"abstain_insufficient_evidence": "⬜ Abstained — insufficient evidence",
             "observed_environmental_hazard": "🟥 Observed environmental hazard (historical evidence)",
             "preliminary_requires_expert_review": "🟨 Preliminary — requires expert review"}[res["assessment_status"]]
    st.markdown(f"**Status:** {badge}")
    st.info(res["recommendation"])
    for w in res["warnings"][1:]:
        st.warning(w)

    def table(rows):
        df = pd.DataFrame([{"layer": r["title"], "status": r["status"], "reading": r["label"], "observed": r["observation"],
                            "res (m)": r["native_resolution_m"], "dist (m)": r["distance_m"]} for r in rows])
        st.dataframe(df, hide_index=True, width="stretch")

    tabs = st.tabs(["Equipment", "Water / wetland", "Terrain", "Soil", "Basin", "Data quality", "Sources"])
    with tabs[0]:
        st.caption("Qualitative research screening only. No crossing probabilities, load limits or routes are produced.")
        for e in res["equipment_screening"]:
            icon, txt = STATE_BADGE[e["state"]]
            with st.expander(f"{icon} {e['label']} — {txt}"):
                if e["warnings"]:
                    st.error(e["warnings"][0])
                if e["observed_hazards"]:
                    st.markdown("**Observed indicators**\n" + "\n".join(f"- {h}" for h in e["observed_hazards"]))
                st.markdown("**Evidence gaps**\n" + "\n".join(f"- {g}" for g in e["evidence_gaps"]))
    with tabs[1]:
        table(res["water_and_wetland"])
        st.caption("Flood extents are past events (2020, 2022) for Hadejia LGA only. No live flood data. Depth unknown.")
    with tabs[2]:
        table(res["visible_terrain"])
        table(res["field_observations"])
        st.caption("'Soil' / 'Bare soil' map classes mean exposed ground surface, not sand.")
    with tabs[3]:
        s = res["soil_composition"]
        st.markdown(f"**Sand / silt / clay:** unavailable\n\n{s['reason']}\n\n*Next step:* {s['next_step']}")
    with tabs[4]:
        table(res["basin"])
    with tabs[5]:
        st.json(res["data_quality"])
        for r in res["visible_terrain"] + res["water_and_wetland"] + res["field_observations"] + res["basin"]:
            if r["status"] == "value" and r["caveats"]:
                st.markdown(f"**{r['title']}**\n" + "\n".join(f"- {c}" for c in r["caveats"]))
    with tabs[6]:
        reg = load_registry()
        for s in reg["sources"]:
            link = f"https://doi.org/{s['doi']}" if s.get("doi") else s.get("url", "")
            st.markdown(f"- [{s['title']}]({link}) — {s.get('licence', '?')} — verified: {s.get('verified')}")
        b = reg["boundary"]
        st.markdown(f"- Boundary: {b['title']} — {b['licence']} — {b['attribution']}")

    st.divider()
    js = json.dumps(res, indent=2, default=str)
    rows = []
    for sec in ("visible_terrain", "water_and_wetland", "field_observations", "basin"):
        for r in res[sec]:
            rows.append({"section": sec, **{k: (";".join(v) if isinstance(v, list) else v) for k, v in r.items()}})
    buf = io.StringIO()
    pd.DataFrame(rows).to_csv(buf, index=False)
    c1, c2 = st.columns(2)
    c1.download_button("Export JSON report", js, file_name=f"terrasense_{lat:.4f}_{lon:.4f}.json", mime="application/json")
    c2.download_button("Export CSV (readings)", buf.getvalue(), file_name=f"terrasense_{lat:.4f}_{lon:.4f}.csv", mime="text/csv")
