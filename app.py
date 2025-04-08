# app.py
import streamlit as st
import json
import pandas as pd
import os
import pydeck as pdk
import altair as alt
from datetime import timedelta

st.set_page_config(page_title="Radio Trace Analyzer", layout="wide")
st.title("📡 Radio Trace Analyzer")

# === Radiotyp-Auswahl ===
radio_mode = st.radio("🔊 Wähle Radiotyp", ["DAB", "FM"], index=0)

# === Datei wählen ===
st.subheader("📁 Datenquelle wählen")
data_source = st.radio("Datenquelle", ["Lokale Datei", "Datei hochladen"], horizontal=True)

uploaded_file = None
raw_data = None

if data_source == "Datei hochladen":
    uploaded_file = st.file_uploader("Wähle eine kombinierte JSON-Datei (z. B. dab+gnss.json)", type="json")

    if uploaded_file:
        raw_data = json.load(uploaded_file)
        st.success(f"{len(raw_data)} Einträge aus hochgeladener Datei geladen.")
    else:
        st.warning("Bitte lade eine Datei hoch.")
        st.stop()
else:
    PRELOADED_PATH = "assets/dab+gnss.json" if radio_mode == "DAB" else "assets/fm+gnss.json"
    if not os.path.exists(PRELOADED_PATH):
        st.error(f"❌ Datei nicht gefunden: {PRELOADED_PATH}")
        st.stop()
    with open(PRELOADED_PATH, "r", encoding="utf-8") as f:
        raw_data = json.load(f)
    st.success(f"{len(raw_data)} Einträge aus {PRELOADED_PATH} geladen.")


# === Datentrennung ===
def filter_entries(data, typ):
    return [e for e in data if e.get("type") == typ]

radio_data = filter_entries(raw_data, "dab" if radio_mode == "DAB" else "fm")
gnss_data = filter_entries(raw_data, "gnss")

# === Diagramm ===
df = pd.DataFrame(radio_data)
df["timeStamp"] = pd.to_datetime(df["timeStamp"])

st.subheader(f"📊 Diagramm der {radio_mode}-Daten")

if radio_mode == "DAB":
    column_options = ["F_kHz", "RSSI", "SNR"]
else:
    column_options = ["FQ_kHz", "FS", "SNR"]

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

# Dynamische Bewertungshintergründe
if selected_column == "FS" and radio_mode == "FM":
    bands = pd.DataFrame([
        {"y0": 25, "y1": 100, "color": "#d0f0c0"},
        {"y0": 10, "y1": 25, "color": "#fff2cc"},
        {"y0": 0, "y1": 10, "color": "#f4cccc"},
    ])
elif selected_column == "RSSI":
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

# === Farbregeln ===
def rssi_to_color(rssi):
    if pd.isna(rssi):
        return [0, 0, 0]  # Schwarz bei fehlendem Wert
    elif rssi >= -80:
        return [0, 180, 0]
    elif rssi >= -95:
        return [255, 200, 0]
    else:
        return [255, 50, 50]

def snr_to_color(snr):
    if pd.isna(snr):
        return [0, 0, 0]
    elif snr >= 15:
        return [0, 180, 0]
    elif snr >= 8:
        return [255, 200, 0]
    else:
        return [255, 50, 50]

def fs_to_color(fs):
    if pd.isna(fs):
        return [0, 0, 0]
    elif fs >= 25:
        return [0, 180, 0]
    elif fs >= 10:
        return [255, 200, 0]
    else:
        return [255, 50, 50]


def evaluate_single_metric(gnss_df, radio_df, column):
    values = []
    radio_df = radio_df.copy()
    radio_df["timeStamp"] = pd.to_datetime(radio_df["timeStamp"])
    for _, row in gnss_df.iterrows():
        t = row["timeStamp"]
        time_window = radio_df[(radio_df["timeStamp"] >= t - timedelta(seconds=1)) & (radio_df["timeStamp"] <= t + timedelta(seconds=1))]
        val = time_window[column].mean() if not time_window.empty else None
        values.append(val)
    gnss_df = gnss_df.copy()
    gnss_df[column] = values
    return gnss_df

# === Karte ===
st.subheader("📍 GNSS-Daten auf Karte")

map_mode = st.radio("Kartenmodus", ["Standardpunkte", "Nur RSSI anzeigen", "Nur SNR anzeigen", "Nur FS anzeigen"])
style = st.selectbox("🗺️ Kartenstil", [
    "satellite", "light", "dark", "streets", "satellite-streets", "outdoors"
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
gnss_df["timeStr"] = gnss_df["timeStamp"].dt.strftime("%H:%M:%S")

radio_df = pd.DataFrame(radio_data)
radio_df["timeStamp"] = pd.to_datetime(radio_df["timeStamp"])

if map_mode == "Nur RSSI anzeigen" and "RSSI" in radio_df.columns:
    gnss_df = evaluate_single_metric(gnss_df, radio_df, "RSSI")
    gnss_df["color"] = gnss_df["RSSI"].apply(rssi_to_color)
    tooltip_template = "<b>Zeit:</b> {timeStr}<br/><b>RSSI:</b> {RSSI}"
elif map_mode == "Nur SNR anzeigen":
    gnss_df = evaluate_single_metric(gnss_df, radio_df, "SNR")
    gnss_df["color"] = gnss_df["SNR"].apply(snr_to_color)
    tooltip_template = "<b>Zeit:</b> {timeStr}<br/><b>SNR:</b> {SNR}"
elif map_mode == "Nur FS anzeigen" and "FS" in radio_df.columns:
    gnss_df = evaluate_single_metric(gnss_df, radio_df, "FS")
    gnss_df["color"] = gnss_df["FS"].apply(fs_to_color)
    tooltip_template = "<b>Zeit:</b> {timeStr}<br/><b>FS:</b> {FS}"
else:
    gnss_df["color"] = [[255, 0, 0]] * len(gnss_df)
    tooltip_template = "<b>Zeit:</b> {timeStr}"

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
    zoom=15,
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
