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

sorted_sources = sorted(start_times, key=lambda k: start_times[k])
src1, src2 = sorted_sources[0], sorted_sources[1]
start1, start2 = start_times[src1], start_times[src2]

fahrt1_df = radio_df[(radio_df["source"] == src1) & (radio_df["timeStamp"] >= start1) & (radio_df["timeStamp"] < start2)].copy()
fahrt2_df = radio_df[(radio_df["source"] == src2) & (radio_df["timeStamp"] >= start2)].copy()

if "TL" in radio_df.columns:
    radio_df["TL"] = radio_df["TL"].apply(lambda x: int(str(x)[-2:]) if pd.notnull(x) else None)
    fahrt1_df["TL"] = fahrt1_df["TL"].apply(lambda x: int(str(x)[-2:]) if pd.notnull(x) else None)
    fahrt2_df["TL"] = fahrt2_df["TL"].apply(lambda x: int(str(x)[-2:]) if pd.notnull(x) else None)

fahrt1_df["time_rel"] = (fahrt1_df["timeStamp"] - start1).dt.total_seconds()
fahrt2_df["time_rel"] = (fahrt2_df["timeStamp"] - start2).dt.total_seconds()

# === Diagramm ===
st.subheader("📊 Vergleichsdiagramm der Fahrten")

if radio_mode == "DAB":
    selected_metric = "TL"
    st.markdown("**Angezeigte Metrik:** `TL` (Transmission Level)")
else:
    selected_metric = "FS"
    st.markdown("**Angezeigte Metrik:** `FS` (Field Strength)")


resample = st.selectbox("Zeitintervall (für Mittelwert)", ["Original", "1s", "5s", "10s"])
show_points = st.checkbox("Punkte anzeigen", value=True)
show_avg = st.checkbox("Durchschnitt anzeigen")
show_trend = st.checkbox("Tendenzlinien anzeigen")

chart_data = []
for df, src in zip([fahrt1_df, fahrt2_df], [src1, src2]):
    sub = df.set_index("timeStamp")[[selected_metric, "time_rel"]]
    if resample != "Original":
        sub = sub.resample(resample).mean().dropna()
    sub["source"] = src
    sub.reset_index(inplace=True)
    chart_data.append(sub)

combined_df = pd.concat(chart_data)
x_axis = alt.X("time_rel:Q", title="Zeit seit Referenzpunkt [s]")
layers = []

if show_points:
    base = alt.Chart(combined_df).mark_circle(size=30).encode(
        x=x_axis,
        y=alt.Y(selected_metric, title=selected_metric),
        color=alt.Color("source:N", title="Fahrt"),
        tooltip=[
            alt.Tooltip("timeStamp:T", title="Zeit", format="%H:%M:%S.%L"),
            alt.Tooltip(f"{selected_metric}:Q", title=selected_metric),
            alt.Tooltip("source:N", title="Fahrt")
        ]
    )
    layers.append(base)

if show_avg:
    for src in [src1, src2]:
        mean_val = combined_df[combined_df["source"] == src][selected_metric].mean()
        rule = alt.Chart(pd.DataFrame({"y": [mean_val]})).mark_rule(
            strokeDash=[4, 2], color="gray"
        ).encode(y="y")
        layers.append(rule)

if show_trend:
    for src in [src1, src2]:
        trend_data = combined_df[combined_df["source"] == src]
        if len(trend_data) >= 3:
            trend = alt.Chart(trend_data).transform_loess(
                "time_rel", selected_metric, bandwidth=0.3, groupby=["source"]
            ).mark_line().encode(
                x=x_axis,
                y=selected_metric,
                color=alt.Color("source:N", legend=None),
                tooltip=[
                    alt.Tooltip("source:N", title="Fahrt"),
                    alt.Tooltip("time_rel:Q", title="Zeit [s]"),
                    alt.Tooltip(f"{selected_metric}:Q", title=selected_metric)
                ]
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

    def snr_to_color(snr):
        if pd.isna(snr): return [50, 50, 50]
        elif snr >= 15: return [0, 180, 0]
        elif snr >= 8: return [255, 200, 0]
        else: return [255, 50, 50]

    def tl_to_color(tl):
        if pd.isna(tl): return [50, 50, 50]
        elif tl >= 70: return [0, 180, 0]
        elif tl >= 50: return [255, 200, 0]
        else: return [255, 50, 50]

    def score_to_color(score):
        if pd.isna(score): return [50, 50, 50]
        elif score >= 66: return [0, 180, 0]
        elif score >= 33: return [255, 200, 0]
        else: return [255, 50, 50]

    gnss_df["timeStamp"] = pd.to_datetime(gnss_df["timeStamp"])
    radio_df["timeStamp"] = pd.to_datetime(radio_df["timeStamp"])
    gnss_df["timeStr"] = gnss_df["timeStamp"].dt.strftime("%H:%M:%S.%f")

    # Neue Logik: Mittelwert aus Zeitbereich GNSS_prev -> GNSS_now
    def evaluate_by_interval(df, radio_df, column, color_func):
        df = df.sort_values("timeStamp").reset_index(drop=True)
        result_vals = []
        result_colors = []

        for idx in range(len(df)):
            curr_row = df.iloc[idx]
            if idx == 0:
                result_vals.append(None)
                result_colors.append([50, 50, 50])
                continue
            prev_time = df.iloc[idx - 1]["timeStamp"]
            curr_time = curr_row["timeStamp"]

            subset = radio_df[
                (radio_df["source"] == curr_row["source"]) &
                (radio_df["timeStamp"] > prev_time) &
                (radio_df["timeStamp"] <= curr_time)
            ]

            val = subset[column].mean() if not subset.empty else None
            result_vals.append(val)
            result_colors.append(color_func(val) if pd.notna(val) else [50, 50, 50])

        df[column] = result_vals
        df["color"] = result_colors
        return df

    def evaluate_score_interval(df, radio_df):
        df = df.sort_values("timeStamp").reset_index(drop=True)
        scores = []
        colors = []

        for idx in range(len(df)):
            curr_row = df.iloc[idx]
            if idx == 0:
                scores.append(None)
                colors.append([50, 50, 50])
                continue
            prev_time = df.iloc[idx - 1]["timeStamp"]
            curr_time = curr_row["timeStamp"]

            subset = radio_df[
                (radio_df["source"] == curr_row["source"]) &
                (radio_df["timeStamp"] > prev_time) &
                (radio_df["timeStamp"] <= curr_time)
            ]

            if subset.empty:
                scores.append(None)
                colors.append([50, 50, 50])
            else:
                snr = subset["SNR"].mean() if "SNR" in subset.columns else None
                tl = subset["TL"].mean() if "TL" in subset.columns else None
                snr_score = min(snr / 20, 1) * 100 if pd.notnull(snr) else 0
                tl_score = min(max((tl + 100) / 30, 0), 1) * 100 if pd.notnull(tl) else 0
                score = 0.5 * snr_score + 0.5 * tl_score
                scores.append(score)
                colors.append(score_to_color(score))

        df["score"] = scores
        df["color"] = colors
        return df

    # Map Mode
    if map_mode == "Signalqualität bewerten (Score)":
        gnss_df = evaluate_score_interval(gnss_df, radio_df)
        tooltip_html = "<b>Zeit:</b> {timeStr}<br/><b>Score:</b> {score:.1f}"
    elif map_mode == "Nur SNR anzeigen":
        gnss_df = evaluate_by_interval(gnss_df, radio_df, "SNR", snr_to_color)
        tooltip_html = "<b>Zeit:</b> {timeStr}<br/><b>SNR:</b> {SNR}"
    elif map_mode == "Nur TL anzeigen" or map_mode == "Nur FS anzeigen":
        column = "TL" if "TL" in radio_df.columns else "FS"
        color_func = tl_to_color if column == "TL" else snr_to_color
        gnss_df = evaluate_by_interval(gnss_df, radio_df, column, color_func)
        tooltip_html = f"<b>Zeit:</b> {{timeStr}}<br/><b>{column}:</b> "+"{"+column+"}"
    else:
        gnss_df["color"] = [[255, 0, 0]] * len(gnss_df)
        tooltip_html = "<b>Zeit:</b> {timeStr}"

    # Karte anzeigen
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
