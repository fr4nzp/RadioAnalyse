import streamlit as st
import json
import pandas as pd
import os
import re
import pydeck as pdk
import altair as alt
from datetime import timedelta

st.set_page_config(page_title="Radio Trace Analyzer", layout="wide")
st.title("📡 Radio Trace Analyzer")

# Hilfsfunktionen
def filter_entries(data, typ):
    return [e for e in data if e.get("type") == typ]

def evaluate_single_metric(gnss_df, radio_df, column):
    values = []
    radio_df["timeStamp"] = pd.to_datetime(radio_df["timeStamp"])
    for _, row in gnss_df.iterrows():
        t = row["timeStamp"]
        window = radio_df[(radio_df["timeStamp"] >= t - timedelta(seconds=1)) & (radio_df["timeStamp"] <= t + timedelta(seconds=1))]
        values.append(window[column].mean() if not window.empty else None)
    gnss_df[column] = values
    return gnss_df

def score_to_color(val):
    if pd.isna(val): return [0, 0, 0]
    elif val >= 0.66: return [0, 180, 0]
    elif val >= 0.33: return [255, 200, 0]
    else: return [255, 50, 50]

def rssi_to_color(val):
    if pd.isna(val): return [0, 0, 0]
    elif val >= -80: return [0, 180, 0]
    elif val >= -95: return [255, 200, 0]
    else: return [255, 50, 50]

def snr_to_color(val):
    if pd.isna(val): return [0, 0, 0]
    elif val >= 15: return [0, 180, 0]
    elif val >= 8: return [255, 200, 0]
    else: return [255, 50, 50]

# Datei-Auswahl
available_files = [f for f in os.listdir("data") if f.endswith(".parsed.json")]
selected_files = st.multiselect("Wähle eine oder mehrere analysierte Dateien", available_files, default=available_files[:1])

if not selected_files:
    st.warning("Bitte mindestens eine Datei auswählen.")
    st.stop()

radio_mode = st.radio("Welche Radiodaten möchtest du analysieren?", ["DAB", "FM"])

# Daten einlesen
all_radio = []
all_gnss = []
for file in selected_files:
    with open(os.path.join("data", file), "r", encoding="utf-8") as f:
        raw_data = json.load(f)
    data_source = os.path.splitext(file)[0]
    radio = filter_entries(raw_data, "dab" if radio_mode == "DAB" else "fm")
    for entry in radio:
        entry["source"] = data_source
    gnss = filter_entries(raw_data, "gnss")
    for entry in gnss:
        entry["source"] = data_source
    all_radio.extend(radio)
    all_gnss.extend(gnss)

radio_df = pd.DataFrame(all_radio)
gnss_df = pd.DataFrame(all_gnss)

# ==================== Diagramm ====================
# ==================== Diagramm ====================
from geopy.distance import geodesic

st.subheader("📊 Radiodaten als Diagramm")

if radio_df.empty or gnss_df.empty:
    st.warning("Keine passenden Daten gefunden.")
else:
    radio_df["timeStamp"] = pd.to_datetime(radio_df["timeStamp"])
    gnss_df["timeStamp"] = pd.to_datetime(gnss_df["timeStamp"])

    # Umschalter für Achse
    use_gnss_xaxis = st.checkbox("X-Achse: Strecke statt Zeit", value=False)

    # Distanzberechnung je Quelle
    def compute_gnss_distance(df):
        df = df.sort_values("timeStamp").reset_index(drop=True)
        distances = [0]
        for i in range(1, len(df)):
            p1 = (df.loc[i-1, "lat"], df.loc[i-1, "lon"])
            p2 = (df.loc[i, "lat"], df.loc[i, "lon"])
            d = geodesic(p1, p2).meters
            distances.append(distances[-1] + d)
        df["distance_m"] = distances
        return df

    gnss_df = gnss_df.groupby("source", group_keys=False).apply(compute_gnss_distance)

    # Radiodaten mit nächster GNSS-Distanz verknüpfen
    def find_nearest_distance(row):
        subset = gnss_df[gnss_df["source"] == row["source"]]
        nearest_idx = (subset["timeStamp"] - row["timeStamp"]).abs().idxmin()
        return subset.loc[nearest_idx, "distance_m"]

    radio_df["distance_m"] = radio_df.apply(find_nearest_distance, axis=1)

    # Metriken
    metric_cols = ["SNR", "RSSI"] if radio_mode == "DAB" else ["SNR", "FS"]
    selected_metric = st.selectbox("Welche Metrik möchtest du anzeigen?", metric_cols)

    resample = st.selectbox("Zeitintervall (für Mittelwert)", ["Original", "1s", "5s", "10s"])
    show_points = st.checkbox("Punkte anzeigen", value=True)
    show_avg = st.checkbox("Durchschnitt anzeigen")
    show_trend = st.checkbox("Tendenzlinien anzeigen")

    chart_data = []
    for src in radio_df["source"].unique():
        sub = radio_df[radio_df["source"] == src].copy()
        sub = sub.set_index("timeStamp")[[selected_metric, "distance_m"]]
        if resample != "Original":
            sub = sub.resample(resample).mean().dropna()
        sub["source"] = src
        sub.reset_index(inplace=True)
        chart_data.append(sub)

    combined_df = pd.concat(chart_data)

    # X-Achse wählen
    x_axis = alt.X("distance_m:Q", title="Strecke [m]") if use_gnss_xaxis else alt.X("timeStamp:T", title="Zeit")

    layers = []

    if show_points:
        base = alt.Chart(combined_df).mark_circle(size=30).encode(
            x=x_axis,
            y=alt.Y(selected_metric, title=selected_metric),
            color="source:N",
            tooltip=["timeStamp:T", selected_metric, "source"]
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
                color=alt.value("black")
            ).properties(title=f"Tendenzlinie: {src}")
            layers.append(trend)

    st.altair_chart(alt.layer(*layers).interactive(), use_container_width=True)


# ==================== Karte ====================
st.subheader("📍 GNSS-Karte")

map_mode = st.radio("Farbkodierung", ["Nur SNR", "Nur RSSI", "Signalqualität kombiniert"])
style = st.selectbox("🗺️ Kartenstil", ["streets", "light", "dark", "satellite", "outdoors"])
style_dict = {
    "streets": "mapbox://styles/mapbox/streets-v11",
    "light": "mapbox://styles/mapbox/light-v10",
    "dark": "mapbox://styles/mapbox/dark-v10",
    "satellite": "mapbox://styles/mapbox/satellite-v9",
    "outdoors": "mapbox://styles/mapbox/outdoors-v11"
}
map_style = style_dict[style]

gnss_df["timeStamp"] = pd.to_datetime(gnss_df["timeStamp"])
gnss_df["timeStr"] = gnss_df["timeStamp"].dt.strftime("%H:%M:%S")

radio_df["timeStamp"] = pd.to_datetime(radio_df["timeStamp"])
mid_lat = gnss_df["lat"].mean()
mid_lon = gnss_df["lon"].mean()

color_column = None

for src in gnss_df["source"].unique():
    gnss_part = gnss_df[gnss_df["source"] == src]
    radio_part = radio_df[radio_df["source"] == src]

    if map_mode == "Nur SNR":
        gnss_part = evaluate_single_metric(gnss_part, radio_part, "SNR")
        gnss_df.loc[gnss_part.index, "color"] = gnss_part["SNR"].apply(snr_to_color)
        tooltip = "<b>Zeit:</b> {timeStr}<br/><b>SNR:</b> {SNR}"
    elif map_mode == "Nur RSSI":
        gnss_part = evaluate_single_metric(gnss_part, radio_part, "RSSI")
        gnss_df.loc[gnss_part.index, "color"] = gnss_part["RSSI"].apply(rssi_to_color)
        tooltip = "<b>Zeit:</b> {timeStr}<br/><b>RSSI:</b> {RSSI}"
    else:
        gnss_part = evaluate_single_metric(gnss_part, radio_part, "SNR")
        gnss_part = evaluate_single_metric(gnss_part, radio_part, "RSSI")
        snr = gnss_part["SNR"]
        rssi = gnss_part["RSSI"]
        score = 0.5 * snr.fillna(0) / 20 + 0.5 * (rssi.fillna(-120) + 100) / 20
        score = score.clip(0, 1)
        gnss_df.loc[gnss_part.index, "color"] = score.apply(score_to_color)
        tooltip = "<b>Zeit:</b> {timeStr}<br/><b>Score:</b> {score:.2f}"

layer = pdk.Layer(
    "ScatterplotLayer",
    data=gnss_df,
    get_position="[lon, lat]",
    get_radius=6,
    get_fill_color="color",
    pickable=True
)

view_state = pdk.ViewState(latitude=mid_lat, longitude=mid_lon, zoom=14)
deck = pdk.Deck(
    layers=[layer],
    initial_view_state=view_state,
    map_style=map_style,
    tooltip={"html": tooltip, "style": {"backgroundColor": "white", "color": "black"}}
)

st.pydeck_chart(deck)

with st.expander("📋 GNSS-Daten anzeigen"):
    st.dataframe(gnss_df)
