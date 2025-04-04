# app.py
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

# Hilfsfunktionen zur Extraktion aus kombinierten Daten
def filter_entries(data, typ):
    return [e for e in data if e.get("type") == typ]

def evaluate_signal_quality(gnss_df, radio_df):
    scores = []
    radio_df = radio_df.copy()
    radio_df["timeStamp"] = pd.to_datetime(radio_df["timeStamp"])
    for _, row in gnss_df.iterrows():
        t = row["timeStamp"]
        time_window = radio_df[(radio_df["timeStamp"] >= t - timedelta(seconds=1)) & (radio_df["timeStamp"] <= t + timedelta(seconds=1))]
        if not time_window.empty:
            snr = time_window["SNR"].mean()
            rssi = time_window["RSSI"].mean()
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
    radio_df["timeStamp"] = pd.to_datetime(radio_df["timeStamp"])
    for _, row in gnss_df.iterrows():
        t = row["timeStamp"]
        time_window = radio_df[(radio_df["timeStamp"] >= t - timedelta(seconds=1)) & (radio_df["timeStamp"] <= t + timedelta(seconds=1))]
        if not time_window.empty:
            val = time_window[column].mean()
        else:
            val = None
        values.append(val)
    gnss_df = gnss_df.copy()
    gnss_df[column] = values
    return gnss_df

def rssi_to_color(rssi):
    if rssi is None:
        return [128, 128, 128]
    elif rssi >= -80:
        return [0, 180, 0]
    elif rssi >= -95:
        return [255, 200, 0]
    else:
        return [255, 50, 50]

def snr_to_color(snr):
    if snr is None:
        return [128, 128, 128]
    elif snr >= 15:
        return [0, 180, 0]
    elif snr >= 8:
        return [255, 200, 0]
    else:
        return [255, 50, 50]

def score_to_color(score):
    if score is None:
        return [128, 128, 128]
    elif score < 33:
        return [255, 50, 50]
    elif score < 66:
        return [255, 200, 0]
    else:
        return [0, 180, 0]

def make_tooltip_df(df, columns):
    df = df.copy()
    for col in columns:
        if col not in df:
            df[col] = None
    return df

# Datei laden
PRELOADED_PATH = "assets/dab+gnss.json"
if os.path.exists(PRELOADED_PATH):
    with open(PRELOADED_PATH, "r", encoding="utf-8") as f:
        raw_data = json.load(f)
    st.success(f"{len(raw_data)} Einträge aus {PRELOADED_PATH} geladen.")
else:
    st.error("❌ Keine vorverarbeitete Datei gefunden. Bitte zuerst die Extraktion ausführen.")
    st.stop()

# Daten trennen
dab_data = filter_entries(raw_data, "dab")
gnss_data = filter_entries(raw_data, "gnss")

# === Diagramm ===
if dab_data:
    df = pd.DataFrame(dab_data)
    df["timeStamp"] = pd.to_datetime(df["timeStamp"])

    st.subheader("📊 Diagramm der DAB-Daten")

    column_options = [col for col in df.columns if col not in ["timeStamp", "type"]]
    selected_column = st.selectbox("Welchen Wert möchtest du anzeigen?", column_options)

    resample_interval = st.selectbox("Wähle Zeitintervall (für Mittelwert)", ["Original", "1s", "5s", "10s", "30s", "60s"])
    show_average = st.checkbox("Durchschnittslinie anzeigen")
    show_trend = st.checkbox("Tendenzlinie anzeigen")

    chart_df = df.set_index("timeStamp")[[selected_column]].copy()
    if resample_interval != "Original":
        chart_df = chart_df.resample(resample_interval).mean().dropna()
    chart_df.reset_index(inplace=True)

    base = alt.Chart(chart_df).mark_circle(size=30).encode(
        x="timeStamp:T",
        y=alt.Y(selected_column, title=selected_column),
        tooltip=["timeStamp:T", selected_column]
    )

    layers = []
    if selected_column == "RSSI":
        bands = pd.DataFrame([
            {"y0": -80, "y1": 0, "color": "#d0f0c0"},
            {"y0": -95, "y1": -80, "color": "#fff2cc"},
            {"y0": -120, "y1": -95, "color": "#f4cccc"},
        ])
    elif selected_column == "SNR":
        bands = pd.DataFrame([
            {"y0": 15, "y1": 50, "color": "#d0f0c0"},
            {"y0": 8, "y1": 15, "color": "#fff2cc"},
            {"y0": 0, "y1": 8, "color": "#f4cccc"},
        ])
    else:
        bands = pd.DataFrame([])

    for _, row in bands.iterrows():
        band = alt.Chart(chart_df).mark_rect(opacity=0.2, fill=row.color).encode(
            x="timeStamp:T",
            y=alt.Y("y0:Q"),
            y2="y1:Q"
        ).transform_calculate(
            y0=f"{row['y0']}",
            y1=f"{row['y1']}"
        )
        layers.append(band)

    layers.append(base)
    if show_average:
        mean_value = chart_df[selected_column].mean()
        mean_line = alt.Chart(pd.DataFrame({"y": [mean_value]})).mark_rule(color="green").encode(y="y")
        layers.append(mean_line)
    if show_trend:
        trend_line = base.transform_loess("timeStamp", selected_column, bandwidth=0.3).mark_line(color="orange")
        layers.append(trend_line)

    st.altair_chart(alt.layer(*layers).interactive(), use_container_width=True)
    with st.expander("📋 Zeige Radiodaten als Tabelle"):
        st.dataframe(df)

# === Karte ===
st.subheader("📍 GNSS-Daten auf Karte")
map_mode = st.radio("Kartenmodus", ["Standardpunkte", "Signalqualität bewerten", "Nur RSSI anzeigen", "Nur SNR anzeigen"])
style = st.selectbox("🗺️ Wähle Kartenstil", [
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
map_style = style_dict[style]

gnss_df = pd.DataFrame(gnss_data)
gnss_df["timeStamp"] = pd.to_datetime(gnss_df["timeStamp"])
gnss_df["timeStr"] = gnss_df["timeStamp"].dt.strftime("%Y-%m-%d %H:%M:%S.%f")
mid_lat = gnss_df["lat"].mean()
mid_lon = gnss_df["lon"].mean()

radio_df = pd.DataFrame(dab_data)
radio_df["timeStamp"] = pd.to_datetime(radio_df["timeStamp"])

if map_mode == "Signalqualität bewerten":
    gnss_df = evaluate_signal_quality(gnss_df, radio_df)
    gnss_df["color"] = gnss_df["signal_score"].apply(score_to_color)
    tooltip_template = "<b>Zeit:</b> {timeStr}<br/><b>Score:</b> {signal_score}"
elif map_mode == "Nur RSSI anzeigen":
    gnss_df = evaluate_single_metric(gnss_df, radio_df, "RSSI")
    gnss_df["color"] = gnss_df["RSSI"].apply(rssi_to_color)
    tooltip_template = "<b>Zeit:</b> {timeStr}<br/><b>RSSI:</b> {RSSI}"
elif map_mode == "Nur SNR anzeigen":
    gnss_df = evaluate_single_metric(gnss_df, radio_df, "SNR")
    gnss_df["color"] = gnss_df["SNR"].apply(snr_to_color)
    tooltip_template = "<b>Zeit:</b> {timeStr}<br/><b>SNR:</b> {SNR}"
else:
    gnss_df["color"] = [[255, 0, 0]] * len(gnss_df)
    tooltip_template = "<b>Zeit:</b> {timeStr}"

gnss_df = make_tooltip_df(gnss_df, ["timeStr", "RSSI", "SNR", "signal_score"])

layer = pdk.Layer(
    "ScatterplotLayer",
    data=gnss_df,
    get_position="[lon, lat]",
    get_radius=6,
    get_fill_color="color",
    pickable=True
)

view_state = pdk.ViewState(latitude=mid_lat, longitude=mid_lon, zoom=15, pitch=0)

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

# GNSS Tabelle anzeigen
with st.expander("📋 Zeige GNSS-Daten als Tabelle"):
    st.dataframe(gnss_df)
