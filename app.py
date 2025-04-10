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

# TL Wert bereinigen (z. B. -071 → 71)
if "TL" in radio_df.columns:
    radio_df["TL"] = radio_df["TL"].apply(lambda x: int(str(x)[-2:]) if pd.notnull(x) else None)

metric_cols = ["SNR", "TL"] if radio_mode == "DAB" else ["SNR", "FS"]
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
        color="source:N",
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
    for src in combined_df["source"].unique():
        trend_data = combined_df[combined_df["source"] == src]
        trend = alt.Chart(trend_data).transform_loess(
            "distance_m" if use_gnss_xaxis else "timeStamp",
            selected_metric,
            bandwidth=0.3
        ).mark_line().encode(
            x=x_axis,
            y=selected_metric,
            color="source:N"
        )
        layers.append(trend)

st.altair_chart(alt.layer(*layers).interactive(), use_container_width=True)

# ==================== GNSS Map ====================
st.subheader("📍 GNSS-Daten auf Karte")

if gnss_df.empty:
    st.warning("Keine GNSS-Daten vorhanden.")
else:
    map_mode = st.selectbox("Darstellungsmodus", [
        "Standardpunkte", 
        "Signalqualität bewerten (Score)", 
        "Nur SNR anzeigen", 
        "Nur TL anzeigen" if radio_mode == "DAB" else "Nur FS anzeigen"
    ])

    # Sichtbarkeit pro Quelle
    visible_sources = st.multiselect("Welche Fahrten sollen auf der Karte angezeigt werden?", 
                                     options=gnss_df["source"].unique().tolist(), 
                                     default=gnss_df["source"].unique().tolist())

    gnss_df = gnss_df[gnss_df["source"].isin(visible_sources)].copy()
    radio_df = radio_df[radio_df["source"].isin(visible_sources)].copy()

    # Style-Auswahl
    map_style = st.selectbox("🗺️ Kartenstil", [
        "streets", "light", "dark", "satellite", "satellite-streets", "outdoors"
    ])
    style_dict = {
        "streets": "mapbox://styles/mapbox/streets-v11",
        "light": "mapbox://styles/mapbox/light-v10",
        "dark": "mapbox://styles/mapbox/dark-v10",
        "satellite": "mapbox://styles/mapbox/satellite-v9",
        "satellite-streets": "mapbox://styles/mapbox/satellite-streets-v11",
        "outdoors": "mapbox://styles/mapbox/outdoors-v11"
    }
    map_style_url = style_dict[map_style]

    # Funktionen zur Farbgebung
    def score_to_color(score):
        if score is None:
            return [50, 50, 50]
        elif score >= 66:
            return [0, 180, 0]
        elif score >= 33:
            return [255, 200, 0]
        else:
            return [255, 50, 50]

    def snr_to_color(snr):
        if snr is None:
            return [50, 50, 50]
        elif snr >= 15:
            return [0, 180, 0]
        elif snr >= 8:
            return [255, 200, 0]
        else:
            return [255, 50, 50]

    def tl_to_color(tl):
        if tl is None:
            return [50, 50, 50]
        elif tl >= -70:
            return [0, 180, 0]
        elif tl >= -85:
            return [255, 200, 0]
        else:
            return [255, 50, 50]

    # Metriken berechnen
    def evaluate_metric(df, radio_df, column, color_func):
        values = []
        radio_df["timeStamp"] = pd.to_datetime(radio_df["timeStamp"])
        for _, row in df.iterrows():
            subset = radio_df[radio_df["source"] == row["source"]]
            nearby = subset[(subset["timeStamp"] - row["timeStamp"]).abs() <= timedelta(seconds=1)]
            val = nearby[column].mean() if not nearby.empty else None
            values.append(val)
        df[column] = values
        df["color"] = df[column].apply(color_func)
        return df

    def evaluate_score(df, radio_df):
        scores = []
        for _, row in df.iterrows():
            subset = radio_df[radio_df["source"] == row["source"]]
            nearby = subset[(subset["timeStamp"] - row["timeStamp"]).abs() <= timedelta(seconds=1)]
            if not nearby.empty:
                snr = nearby["SNR"].mean()
                tl = nearby["TL"].mean() if "TL" in nearby.columns else None
                snr_score = min(snr / 20, 1) * 100 if pd.notnull(snr) else 0
                tl_score = min(max((tl + 100) / 30, 0), 1) * 100 if pd.notnull(tl) else 0
                score = 0.5 * snr_score + 0.5 * tl_score
            else:
                score = None
            scores.append(score)
        df["score"] = scores
        df["color"] = df["score"].apply(score_to_color)
        return df

    # Tooltip vorbereiten
    gnss_df["timeStr"] = gnss_df["timeStamp"].dt.strftime("%H:%M:%S.%f")

    if map_mode == "Signalqualität bewerten (Score)":
        gnss_df = evaluate_score(gnss_df, radio_df)
        tooltip_html = "<b>Zeit:</b> {timeStr}<br/><b>Score:</b> {score:.1f}"
    elif map_mode == "Nur SNR anzeigen":
        gnss_df = evaluate_metric(gnss_df, radio_df, "SNR", snr_to_color)
        tooltip_html = "<b>Zeit:</b> {timeStr}<br/><b>SNR:</b> {SNR}"
    elif map_mode == "Nur TL anzeigen" or map_mode == "Nur FS anzeigen":
        col = "TL" if "TL" in radio_df.columns else "FS"
        color_func = tl_to_color if col == "TL" else snr_to_color
        gnss_df = evaluate_metric(gnss_df, radio_df, col, color_func)
        tooltip_html = f"<b>Zeit:</b> {{timeStr}}<br/><b>{col}:</b> "+"{"+col+"}"
    else:
        gnss_df["color"] = [[255, 0, 0]] * len(gnss_df)
        tooltip_html = "<b>Zeit:</b> {timeStr}"

    # PyDeck Layer
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
