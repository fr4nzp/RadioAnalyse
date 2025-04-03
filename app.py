# radio_trace_analyzer/app.py
import streamlit as st
import json
import pandas as pd
import os
import re
import pydeck as pdk
import altair as alt

st.set_page_config(page_title="Radio Trace Analyzer", layout="wide")
st.title("📡 Radio Trace Analyzer")

# Extraktionsfunktionen

def extract_dab(data):
    extracted = []
    for entry in data:
        msg = entry.get("msgData", "")
        if "LRID0x161" in msg or "LRID0x162" in msg:
            match = re.search(r"F=(\d+)kHz.*?RSSI=(-?\d+).*?SNR=(\d+)", msg)
            if match:
                f, rssi, snr = match.groups()
                extracted.append({
                    "timeStamp": entry.get("timeStamp", ""),
                    "F_kHz": int(f),
                    "RSSI": int(rssi),
                    "SNR": int(snr)
                })
    return pd.DataFrame(extracted)

def extract_fm(data):
    extracted = []
    for entry in data:
        msg = entry.get("msgData", "")
        if "T[3/0x232]" in msg or "T[4/0x233]" in msg:
            match = re.search(r"fq (\d+), fs (\d+), snr (\d+)", msg)
            if match:
                fq, fs, snr = match.groups()
                extracted.append({
                    "timeStamp": entry.get("timeStamp", ""),
                    "FQ_kHz": int(fq),
                    "FS": int(fs),
                    "SNR": int(snr)
                })
    return pd.DataFrame(extracted)

def extract_gnss(data):
    extracted = []
    for entry in data:
        msg = entry.get("msgData", "")
        if "TRK-GNSS" in msg:
            match = re.search(r"ts=([\d\.]+), pos=\(([-\d\.]+), ([-\d\.]+),.*?\), hdg=([-\w\.]+), fix=(\d+), antenna=(\d+)", msg)
            if match:
                ts, lat, lon, hdg, fix, antenna = match.groups()
                extracted.append({
                    "timeStamp": entry.get("timeStamp", ""),
                    "ts": float(ts),
                    "lat": float(lat),
                    "lon": float(lon),
                    "hdg": hdg,
                    "fix": int(fix),
                    "antenna": int(antenna)
                })
    return pd.DataFrame(extracted)

# Streamlit UI
uploaded_file = st.file_uploader("Lade eine JSON-Datei mit Trace-Daten hoch", type="json")

if uploaded_file:
    raw_data = json.load(uploaded_file)
    st.success(f"Datei geladen: {len(raw_data)} Einträge gefunden.")

    mode = st.radio("Wähle Radiomodus", ["DAB", "FM"], key="mode_selection")

    df = None
    if mode == "DAB":
        df = extract_dab(raw_data)
    elif mode == "FM":
        df = extract_fm(raw_data)

    if df is not None and not df.empty:
        df["timeStamp"] = pd.to_datetime(df["timeStamp"])

        st.subheader("📊 Diagramm der Radiodaten")

        column_options = [col for col in df.columns if col not in ["timeStamp"]]
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

        # Benchmark-Bänder für DAB
        if mode == "DAB":
            if selected_column == "RSSI":
                bands = pd.DataFrame([
                    {"name": "Gut", "y0": -80, "y1": 0, "color": "#d0f0c0"},
                    {"name": "Mittel", "y0": -95, "y1": -80, "color": "#fff2cc"},
                    {"name": "Schlecht", "y0": -120, "y1": -95, "color": "#f4cccc"},
                ])
            elif selected_column == "SNR":
                bands = pd.DataFrame([
                    {"name": "Gut", "y0": 15, "y1": 50, "color": "#d0f0c0"},
                    {"name": "Mittel", "y0": 8, "y1": 15, "color": "#fff2cc"},
                    {"name": "Schlecht", "y0": 0, "y1": 8, "color": "#f4cccc"},
                ])
            else:
                bands = pd.DataFrame([])

            for _, row in bands.iterrows():
                band = alt.Chart(chart_df).mark_rect(opacity=0.2, fill=row.color).encode(
                    x="timeStamp:T",
                    y=alt.Y("y0:Q", scale=alt.Scale(domain=[bands["y0"].min(), bands["y1"].max()])),
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

    gnss_df = extract_gnss(raw_data)
    gnss_df["timeStamp"] = pd.to_datetime(gnss_df["timeStamp"])
    st.subheader("📍 GNSS-Daten auf Karte")

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

    if not gnss_df.empty:
        mid_lat = gnss_df["lat"].mean()
        mid_lon = gnss_df["lon"].mean()

        layer = pdk.Layer(
            "ScatterplotLayer",
            data=gnss_df,
            get_position="[lon, lat]",
            get_radius=5,
            get_fill_color=[255, 0, 0],
            pickable=True
        )
        view_state = pdk.ViewState(
            latitude=mid_lat,
            longitude=mid_lon,
            zoom=15,
            pitch=0
        )
        st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view_state, map_style=map_style))

    with st.expander("📋 Zeige GNSS-Daten als Tabelle"):
        st.dataframe(gnss_df)
