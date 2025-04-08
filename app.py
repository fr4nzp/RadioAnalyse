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
    selected_files = st.multiselect("Wähle Datendatei(en) aus", available_files, default=available_files[:1])
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

# ==================== Diagramm ====================
st.subheader("📊 Radiodaten als Diagramm")

radio_df["timeStamp"] = pd.to_datetime(radio_df["timeStamp"])
gnss_df["timeStamp"] = pd.to_datetime(gnss_df["timeStamp"])

use_gnss_xaxis = st.checkbox("X-Achse: Strecke statt Zeit", value=False)

# Distanzberechnung mit Anpassung
def compute_gnss_distance_per_fahrt(grouped_df):
    grouped = []
    for src, group in grouped_df.groupby("source"):
        group = group.sort_values("timeStamp").reset_index(drop=True)
        distances = [0]
        for i in range(1, len(group)):
            p1 = (group.loc[i-1, "lat"], group.loc[i-1, "lon"])
            p2 = (group.loc[i, "lat"], group.loc[i, "lon"])
            d = geodesic(p1, p2).meters
            distances.append(distances[-1] + d)
        group["distance_local"] = distances
        grouped.append(group)

    combined = pd.concat(grouped)
    min_starts = {src: group["distance_local"].min() for src, group in combined.groupby("source")}
    global_offset = min(min_starts.values())

    combined["distance_m"] = combined.apply(
        lambda row: row["distance_local"] + (min_starts[row["source"]] - global_offset), axis=1
    )
    return combined

gnss_df = compute_gnss_distance_per_fahrt(gnss_df)

def find_nearest_distance(row):
    subset = gnss_df[gnss_df["source"] == row["source"]]
    nearest_idx = (subset["timeStamp"] - row["timeStamp"]).abs().idxmin()
    return subset.loc[nearest_idx, "distance_m"]

radio_df["distance_m"] = radio_df.apply(find_nearest_distance, axis=1)
radio_df = radio_df.merge(
    gnss_df[["timeStamp", "source", "lat", "lon"]],
    on=["timeStamp", "source"], how="left"
)

metric_cols = ["SNR", "RSSI"] if radio_mode == "DAB" else ["SNR", "FS"]
selected_metric = st.selectbox("Welche Metrik möchtest du anzeigen?", metric_cols)
resample = st.selectbox("Zeitintervall (für Mittelwert)", ["Original", "1s", "5s", "10s"])
show_points = st.checkbox("Punkte anzeigen", value=True)
show_avg = st.checkbox("Durchschnitt anzeigen")
show_trend = st.checkbox("Tendenzlinien anzeigen")

chart_data = []
for src in radio_df["source"].unique():
    sub = radio_df[radio_df["source"] == src].copy()
    sub = sub.set_index("timeStamp")[[selected_metric, "distance_m", "lat", "lon"]]
    if resample != "Original":
        sub = sub.resample(resample).mean().dropna()
    sub["source"] = src
    sub.reset_index(inplace=True)
    chart_data.append(sub)

combined_df = pd.concat(chart_data)
x_axis = alt.X("distance_m:Q", title="Strecke [m]") if use_gnss_xaxis else alt.X("timeStamp:T", title="Zeit")
layers = []

if show_points:
    base = alt.Chart(combined_df).mark_circle(size=30).encode(
        x=x_axis,
        y=alt.Y(selected_metric, title=selected_metric),
        color=alt.Color("source:N", title="Quelle"),
        tooltip=[
            alt.Tooltip("timeStamp:T", title="Zeit", format="%H:%M:%S.%L"),
            alt.Tooltip("lat:Q", title="Latitude"),
            alt.Tooltip("lon:Q", title="Longitude"),
            alt.Tooltip(f"{selected_metric}:Q", title=selected_metric),
            alt.Tooltip("source:N", title="Quelle")
        ]
    )
    layers.append(base)

if show_avg:
    for src in combined_df["source"].unique():
        mean_val = combined_df[combined_df["source"] == src][selected_metric].mean()
        rule = alt.Chart(pd.DataFrame({"y": [mean_val]})).mark_rule(
            strokeDash=[4,2], color="gray"
        ).encode(y="y")
        layers.append(rule)

if show_trend:
    trend = alt.Chart(combined_df).transform_loess(
        "distance_m" if use_gnss_xaxis else "timeStamp",
        selected_metric,
        groupby=["source"],
        bandwidth=0.3
    ).mark_line().encode(
        x=x_axis,
        y=alt.Y(selected_metric, title=selected_metric),
        color=alt.Color("source:N", title="Quelle")
    )
    layers.append(trend)

st.altair_chart(alt.layer(*layers).interactive(), use_container_width=True)


# ==================== Karte ====================
st.subheader("📍 GNSS-Daten auf Karte")

map_mode = st.radio("Kartenmodus", ["Standardpunkte", "Signalqualität bewerten", "Nur RSSI anzeigen", "Nur SNR anzeigen"])
style = st.selectbox("🗺️ Wähle Kartenstil", ["satellite","streets", "light", "dark",  "satellite-streets", "outdoors"])
style_dict = {
        "satellite": "mapbox://styles/mapbox/satellite-v9",
    "streets": "mapbox://styles/mapbox/streets-v11",
    "light": "mapbox://styles/mapbox/light-v10",
    "dark": "mapbox://styles/mapbox/dark-v10",
    "satellite-streets": "mapbox://styles/mapbox/satellite-streets-v11",
    "outdoors": "mapbox://styles/mapbox/outdoors-v11"
}
map_style = style_dict[style]

def score_to_color(score):
    if score is None: return [0, 0, 0]
    elif score < 33: return [255, 50, 50]
    elif score < 66: return [255, 200, 0]
    else: return [0, 180, 0]

def rssi_to_color(rssi):
    if rssi is None: return [0, 0, 0]
    elif rssi >= -80: return [0, 180, 0]
    elif rssi >= -95: return [255, 200, 0]
    else: return [255, 50, 50]

def snr_to_color(snr):
    if snr is None: return [0, 0, 0]
    elif snr >= 15: return [0, 180, 0]
    elif snr >= 8: return [255, 200, 0]
    else: return [255, 50, 50]

def evaluate_signal_quality(gnss_df, radio_df):
    scores = []
    radio_df = radio_df.copy()
    for _, row in gnss_df.iterrows():
        t = row["timeStamp"]
        subset = radio_df[(radio_df["timeStamp"] >= t - timedelta(seconds=1)) & (radio_df["timeStamp"] <= t + timedelta(seconds=1)) & (radio_df["source"] == row["source"])]
        if not subset.empty:
            snr = subset["SNR"].mean()
            rssi = subset["RSSI"].mean() if "RSSI" in subset else None
            snr_score = min(snr / 20, 1) * 100 if pd.notnull(snr) else 0
            rssi_score = min(max((rssi + 100) / 20, 0), 1) * 100 if pd.notnull(rssi) else 0
            score = round(0.5 * snr_score + 0.5 * rssi_score, 1)
        else:
            score = None
        scores.append(score)
    gnss_df = gnss_df.copy()
    gnss_df["signal_score"] = scores
    return gnss_df

def evaluate_single_metric(gnss_df, radio_df, column):
    values = []
    radio_df = radio_df.copy()
    for _, row in gnss_df.iterrows():
        t = row["timeStamp"]
        subset = radio_df[(radio_df["timeStamp"] >= t - timedelta(seconds=1)) & (radio_df["timeStamp"] <= t + timedelta(seconds=1)) & (radio_df["source"] == row["source"])]
        if not subset.empty:
            val = subset[column].mean()
        else:
            val = None
        values.append(val)
    gnss_df = gnss_df.copy()
    gnss_df[column] = values
    return gnss_df

gnss_df["timeStr"] = gnss_df["timeStamp"].dt.strftime("%H:%M:%S")

if map_mode == "Signalqualität bewerten":
    gnss_df = evaluate_signal_quality(gnss_df, radio_df)
    gnss_df["color"] = gnss_df["signal_score"].apply(score_to_color)
    gnss_df["value"] = gnss_df["signal_score"]
    metric = "Score"
elif map_mode == "Nur RSSI anzeigen":
    gnss_df = evaluate_single_metric(gnss_df, radio_df, "RSSI")
    gnss_df["color"] = gnss_df["RSSI"].apply(rssi_to_color)
    gnss_df["value"] = gnss_df["RSSI"]
    metric = "RSSI"
elif map_mode == "Nur SNR anzeigen":
    gnss_df = evaluate_single_metric(gnss_df, radio_df, "SNR")
    gnss_df["color"] = gnss_df["SNR"].apply(snr_to_color)
    gnss_df["value"] = gnss_df["SNR"]
    metric = "SNR"
else:
    gnss_df["color"] = [[255, 0, 0]] * len(gnss_df)
    gnss_df["value"] = None
    metric = ""

tooltip_template = (
    "<b>Zeit:</b> {{timeStr}}<br/>"
    "<b>Lat:</b> {{lat}}<br/>"
    "<b>Lon:</b> {{lon}}<br/>"
    "<b>{metric}:</b> {{value}}"
).format(metric=metric)

layer = pdk.Layer(
    "ScatterplotLayer",
    data=gnss_df,
    get_position="[lon, lat]",
    get_radius=6,
    get_fill_color="color",
    pickable=True
)

view_state = pdk.ViewState(
    latitude=gnss_df["lat"].mean(),
    longitude=gnss_df["lon"].mean(),
    zoom=14,
    pitch=0
)

deck = pdk.Deck(
    layers=[layer],
    initial_view_state=view_state,
    map_style=map_style,
    tooltip={
        "html": tooltip_template,
        "style": {"backgroundColor": "white", "color": "black"}
    }
)

st.pydeck_chart(deck)

with st.expander("📋 Zeige GNSS-Daten als Tabelle"):
    st.dataframe(gnss_df)
