import streamlit as st
import json
import pandas as pd
import os
import re
import pydeck as pdk
import altair as alt
from datetime import timedelta
from geopy.distance import geodesic

st.set_page_config(page_title="Radio Trace Analyzer", layout="wide")
st.title("📡 Radio Trace Analyzer")

# === Datei auswählen ===
use_uploaded = st.checkbox("Eigene Datei hochladen")

if use_uploaded:
    uploaded_file = st.file_uploader("Wähle eine JSON-Datei", type="json")
    if uploaded_file is None:
        st.stop()
    raw_data = json.load(uploaded_file)
    selected_sources = ["Upload"]
    for entry in raw_data:
        entry["source"] = "Upload"
else:
    available_files = [f for f in os.listdir("data") if f.endswith(".json")]
    selected_files = st.multiselect("Wähle Datendatei(en) aus", available_files, default=available_files[:2])
    if not selected_files:
        st.stop()
    raw_data = []
    selected_sources = []
    for file in selected_files:
        path = os.path.join("data", file)
        with open(path, "r", encoding="utf-8") as f:
            part = json.load(f)
            source_name = os.path.splitext(file)[0]
            for entry in part:
                entry["source"] = source_name
            raw_data.extend(part)
        selected_sources.append(source_name)

# === Daten vorbereiten ===
def filter_entries(data, typ):
    return [e for e in data if e.get("type") == typ]

radio_mode = st.radio("Radiomodus", ["DAB", "FM"], horizontal=True)
radio_data = filter_entries(raw_data, "dab" if radio_mode == "DAB" else "fm")
gnss_data = filter_entries(raw_data, "gnss")

radio_df = pd.DataFrame(radio_data)
gnss_df = pd.DataFrame(gnss_data)

if radio_df.empty or gnss_df.empty:
    st.warning("Nicht genügend Daten vorhanden.")
    st.stop()

radio_df["timeStamp"] = pd.to_datetime(radio_df["timeStamp"])
gnss_df["timeStamp"] = pd.to_datetime(gnss_df["timeStamp"])

# Automatische Auswahl eines Referenzpunkts
shortest = gnss_df.groupby("source").size().idxmin()
ref_start = gnss_df[gnss_df["source"] == shortest].iloc[0][["lat", "lon"]].values

def get_start_timestamp_near_ref(gnss_df, source, ref_point):
    df = gnss_df[gnss_df["source"] == source].copy()
    df["distance_to_ref"] = df.apply(lambda row: geodesic((row["lat"], row["lon"]), ref_point).meters, axis=1)
    nearest = df.loc[df["distance_to_ref"].idxmin()]
    return nearest["timeStamp"]

# === Start-Zeitpunkte ermitteln ===
start_times = {}
for src in radio_df["source"].unique():
    gnss_time = get_start_timestamp_near_ref(gnss_df, src, ref_start)
    sub_radio = radio_df[radio_df["source"] == src]
    radio_after_gnss = sub_radio[sub_radio["timeStamp"] >= gnss_time]
    if not radio_after_gnss.empty:
        radio_start = radio_after_gnss.iloc[0]["timeStamp"]
    else:
        radio_start = sub_radio.iloc[0]["timeStamp"]
    start_times[src] = radio_start

# === Robust sortieren und Fahrten zuweisen ===
sorted_sources = sorted(start_times, key=lambda k: start_times[k])

if len(sorted_sources) >= 2:
    src1, src2 = sorted_sources[0], sorted_sources[1]
    start1, start2 = start_times[src1], start_times[src2]

    fahrt1_df = radio_df[(radio_df["source"] == src1) & (radio_df["timeStamp"] >= start1) & (radio_df["timeStamp"] < start2)].copy()
    fahrt2_df = radio_df[(radio_df["source"] == src2) & (radio_df["timeStamp"] >= start2)].copy()
elif len(sorted_sources) == 1:
    src1 = sorted_sources[0]
    start1 = start_times[src1]

    fahrt1_df = radio_df[(radio_df["source"] == src1) & (radio_df["timeStamp"] >= start1)].copy()
    fahrt2_df = pd.DataFrame()  # leer lassen
else:
    st.warning("Keine gültigen Fahrten vorhanden.")
    st.stop()

# Zeit normieren
fahrt1_df["time_rel"] = (fahrt1_df["timeStamp"] - start1).dt.total_seconds()
if not fahrt2_df.empty:
    fahrt2_df["time_rel"] = (fahrt2_df["timeStamp"] - start2).dt.total_seconds()


# === Diagramm ===
st.subheader("📊 Vergleichsdiagramm der Fahrten")

# Metrik & Referenzbereiche je nach Radiomodus
if radio_mode == "DAB":
    selected_metric = "TL"
    selected_title = "TL (dBm)"
    reference_ranges = [
        {"label": "Sehr gut", "min": -40, "max": 40, "color": "#c8facc"},
        {"label": "Gut", "min": -60, "max": -40, "color": "#a4e2a0"},
        {"label": "Mittel", "min": -80, "max": -60, "color": "#ffe59d"},
        {"label": "Schlecht", "min": -120, "max": -80, "color": "#f7c2c2"},
    ]
else:
    selected_metric = "FS"
    selected_title = "FS (dBμV)"
    reference_ranges = [
        {"label": "Sehr gut", "min": 60, "max": 120, "color": "#c8facc"},
        {"label": "Gut", "min": 40, "max": 60, "color": "#a4e2a0"},
        {"label": "Mittel", "min": 20, "max": 40, "color": "#ffe59d"},
        {"label": "Schlecht", "min": -20, "max": 20, "color": "#f7c2c2"},
    ]

st.markdown(f"**Angezeigte Metrik:** `{selected_title}`")

# Optionen
resample = st.selectbox("Zeitintervall (für Mittelwert)", ["Original", "1s", "5s", "10s"])
show_points = st.checkbox("Punkte anzeigen", value=True)
show_avg = st.checkbox("Durchschnitt anzeigen")
show_trend = st.checkbox("Tendenzlinien anzeigen")
show_reference = st.checkbox("Referenzbereiche anzeigen")

# Daten vorbereiten
chart_data = []

data_sources = [(fahrt1_df, src1)]
if not fahrt2_df.empty:
    data_sources.append((fahrt2_df, src2))

for df, src in data_sources:
    sub = df.set_index("timeStamp")[[selected_metric, "time_rel"]]
    if resample != "Original":
        sub = sub.resample(resample).mean().dropna()
    sub["source"] = src
    sub.reset_index(inplace=True)
    chart_data.append(sub)

combined_df = pd.concat(chart_data)

# === Achsen vorbereiten
x_axis = alt.X("time_rel:Q", title="Zeit seit Referenzpunkt [s]")

if selected_metric == "TL":
    min_val = combined_df[selected_metric].min()
    max_val = combined_df[selected_metric].max()
    y_min = min(-100, min_val)
    y_max = max(0, max_val)
    y_axis = alt.Y(selected_metric, title=selected_title, scale=alt.Scale(domain=(y_min, y_max)))
else:
    y_axis = alt.Y(selected_metric, title=selected_title)

# === Diagrammlayer aufbauen
layers = []

# Referenzbereiche als Hintergrund
if show_reference:
    padding = 10  # Sekunden Puffer
    x_min = combined_df["time_rel"].min() - padding
    x_max = combined_df["time_rel"].max() + padding

    for ref in reference_ranges:
        rect = alt.Chart(pd.DataFrame({
            "y_min": [ref["min"]],
            "y_max": [ref["max"]],
            "x_min": [x_min],
            "x_max": [x_max]
        })).mark_rect(opacity=0.2, color=ref["color"]).encode(
            x="x_min:Q",
            x2="x_max:Q",
            y="y_min:Q",
            y2="y_max:Q"
        )
        layers.append(rect)

# Punktdarstellung
if show_points:
    base = alt.Chart(combined_df).mark_circle(size=30).encode(
        x=x_axis,
        y=y_axis,
        color=alt.Color("source:N", title="Fahrt"),
        tooltip=[
            alt.Tooltip("timeStamp:T", title="Zeit", format="%H:%M:%S.%L"),
            alt.Tooltip(f"{selected_metric}:Q", title=selected_title),
            alt.Tooltip("source:N", title="Fahrt")
        ]
    )
    layers.append(base)

# Durchschnittslinien
if show_avg:
    for src in combined_df["source"].unique():
        mean_val = combined_df[combined_df["source"] == src][selected_metric].mean()
        rule = alt.Chart(pd.DataFrame({"y": [mean_val]})).mark_rule(
            strokeDash=[4, 2], color="gray"
        ).encode(y="y")
        layers.append(rule)

# Tendenzlinien (Loess)
if show_trend:
    for src in combined_df["source"].unique():
        trend_data = combined_df[combined_df["source"] == src]
        if len(trend_data) >= 3:
            trend = alt.Chart(trend_data).transform_loess(
                "time_rel", selected_metric, bandwidth=0.3, groupby=["source"]
            ).mark_line().encode(
                x=x_axis,
                y=y_axis,
                color=alt.Color("source:N", legend=None),
                tooltip=[
                    alt.Tooltip("source:N", title="Fahrt"),
                    alt.Tooltip("time_rel:Q", title="Zeit [s]"),
                    alt.Tooltip(f"{selected_metric}:Q", title=selected_title)
                ]
            )
            layers.append(trend)

# Diagramm anzeigen
st.altair_chart(alt.layer(*layers).interactive(), use_container_width=True)


# ==================== GNSS Map ====================
st.subheader("📍 GNSS-Daten auf Karte")

if gnss_df.empty:
    st.warning("Keine GNSS-Daten vorhanden.")
else:
    visible_sources = st.multiselect("Welche Fahrten sollen angezeigt werden?", 
                                     options=gnss_df["source"].unique().tolist(), 
                                     default=gnss_df["source"].unique().tolist())

    gnss_df = gnss_df[gnss_df["source"].isin(visible_sources)].copy()
    radio_df = radio_df[radio_df["source"].isin(visible_sources)].copy()

    map_style = st.selectbox("🗺️ Kartenstil", [
        "satellite", "streets", "light", "dark", "satellite-streets", "outdoors"
    ], index=0)

    style_dict = {
        "streets": "mapbox://styles/mapbox/streets-v11",
        "light": "mapbox://styles/mapbox/light-v10",
        "dark": "mapbox://styles/mapbox/dark-v10",
        "satellite": "mapbox://styles/mapbox/satellite-v9",
        "satellite-streets": "mapbox://styles/mapbox/satellite-streets-v11",
        "outdoors": "mapbox://styles/mapbox/outdoors-v11"
    }
    map_style_url = style_dict[map_style]

    def color_dab_tl(val):
        if pd.isna(val): return [255, 255, 255]
        elif val > -40: return [0, 180, 0]
        elif val > -60: return [160, 220, 100]
        elif val > -80: return [255, 220, 0]
        else: return [255, 70, 70]

    def color_fm_fs(val):
        if pd.isna(val): return [255, 255, 255]
        elif val > 60: return [0, 180, 0]
        elif val > 40: return [160, 220, 100]
        elif val > 20: return [255, 220, 0]
        else: return [255, 70, 70]

    def evaluate_color_interval(df, radio_df, column, color_func):
        df = df.sort_values("timeStamp").reset_index(drop=True)
        values = []
        colors = []

        for idx in range(len(df)):
            curr_row = df.iloc[idx]
            if idx == 0:
                values.append(None)
                colors.append([255, 255, 255])
                continue
            prev_time = df.iloc[idx - 1]["timeStamp"]
            curr_time = curr_row["timeStamp"]

            subset = radio_df[
                (radio_df["source"] == curr_row["source"]) &
                (radio_df["timeStamp"] > prev_time) &
                (radio_df["timeStamp"] <= curr_time)
            ]

            val = subset[column].mean() if not subset.empty else None
            values.append(val)
            colors.append(color_func(val))

        df[column] = values
        df["color"] = colors
        return df

    # GNSS vorbereiten
    gnss_df["timeStamp"] = pd.to_datetime(gnss_df["timeStamp"])
    radio_df["timeStamp"] = pd.to_datetime(radio_df["timeStamp"])
    gnss_df["timeStr"] = gnss_df["timeStamp"].dt.strftime("%H:%M:%S.%f")

    # Modusspezifisch verarbeiten
    if radio_mode == "DAB":
        gnss_df = evaluate_color_interval(gnss_df, radio_df, "TL", color_dab_tl)
        tooltip_html = "<b>Zeit:</b> {timeStr}<br/><b>TL:</b> {TL}"
    else:
        gnss_df = evaluate_color_interval(gnss_df, radio_df, "FS", color_fm_fs)
        tooltip_html = "<b>Zeit:</b> {timeStr}<br/><b>FS:</b> {FS}"

    # Karte rendern
    mid_lat = gnss_df["lat"].mean()
    mid_lon = gnss_df["lon"].mean()

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=gnss_df,
        get_position="[lon, lat]",
        get_radius=6,
        get_fill_color="color",
        pickable=True
    )

    view_state = pdk.ViewState(latitude=mid_lat, longitude=mid_lon, zoom=14)

    st.pydeck_chart(pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        map_style=map_style_url,
        tooltip={"html": tooltip_html, "style": {"color": "black", "backgroundColor": "white"}}
    ))

    with st.expander("📋 GNSS-Tabelle anzeigen"):
        st.dataframe(gnss_df)
