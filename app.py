# radio_trace_analyzer/app.py
import streamlit as st
import json
import pandas as pd
import os
import re

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

    mode = st.radio("Wähle Radiomodus", ["DAB", "FM"])

    if st.button("🔍 Analyse starten"):
        if mode == "DAB":
            df = extract_dab(raw_data)
            st.subheader("📈 DAB-Daten")
            st.dataframe(df)
        elif mode == "FM":
            df = extract_fm(raw_data)
            st.subheader("📈 FM-Daten")
            st.dataframe(df)

        gnss_df = extract_gnss(raw_data)
        st.subheader("📍 GNSS-Daten")
        st.dataframe(gnss_df)
        st.map(gnss_df.rename(columns={"lat": "latitude", "lon": "longitude"}))