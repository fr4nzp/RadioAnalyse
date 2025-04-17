import streamlit as st
import json
import pandas as pd
import altair as alt
import pydeck as pdk
from datetime import datetime
from geopy.distance import geodesic

st.set_page_config(page_title="Analyse", layout="wide")
st.title("🔍 Analysebereich")

# Sicherstellen, dass Daten vorhanden sind
if "uploaded_files" not in st.session_state or not st.session_state.uploaded_files:
    st.warning("⚠️ Du musst zuerst Dateien auf der Startseite hochladen.")
    st.page_link("Home", label="⬅️ Zurück zur Startseite")
    st.stop()

# ---------------------------------------------
# 📁 Sidebar Dateiverwaltung
# ---------------------------------------------
st.sidebar.header("📁 Aktive Fahrten")
for i, file in enumerate(st.session_state.uploaded_files):
    col1, col2 = st.sidebar.columns([4, 1])
    col1.write(f"📄 {file.name}")
    if col2.button("❌", key=f"remove_{i}"):
        st.session_state.uploaded_files.pop(i)
        st.experimental_rerun()

extra = st.sidebar.file_uploader("Weitere Dateien hinzufügen", type="json", accept_multiple_files=True, key="extra_upload")
if extra:
    for file in extra:
        if file.name not in [f.name for f in st.session_state.uploaded_files]:
            st.session_state.uploaded_files.append(file)
    st.experimental_rerun()

if not st.session_state.uploaded_files:
    st.warning("⚠️ Keine Dateien mehr vorhanden.")
    st.page_link("Home", label="⬅️ Zurück zur Startseite")
    st.stop()

# ---------------------------------------------
# 🔄 Daten laden & vorbereiten
# ---------------------------------------------
raw_data = []
for file in st.session_state.uploaded_files:
    file_content = file.read()
    file.seek(0)
    if not file_content.strip():
        st.warning(f"⚠️ Datei '{file.name}' ist leer.")
        continue
    try:
        part = json.loads(file_content)
        for entry in part:
            entry["source"] = file.name
        raw_data.extend(part)
    except json.JSONDecodeError:
        st.error(f"❌ Datei '{file.name}' ist kein gültiges JSON.")
        continue


def filter_entries(data, typ):
    return [e for e in data if e.get("type") == typ]

radio_mode = st.radio("🎙️ Radiomodus", ["DAB", "FM"], horizontal=True)
radio_data = filter_entries(raw_data, "dab" if radio_mode == "DAB" else "fm")
gnss_data = filter_entries(raw_data, "gnss")

radio_df = pd.DataFrame(radio_data)
gnss_df = pd.DataFrame(gnss_data)

# 📻 Frequenzfilter bei DAB
if radio_mode == "DAB" and "F_kHz" in radio_df.columns:
    freq_counts = radio_df["F_kHz"].value_counts().sort_index()
    freq_options = [f"{freq} kHz ({count})" for freq, count in freq_counts.items()]
    freq_map = dict(zip(freq_options, freq_counts.index))

    if len(freq_options) > 1:
        selected_label = st.selectbox("🎚️ Frequenz auswählen (kHz):", freq_options)
        selected_freq = freq_map[selected_label]
        radio_df = radio_df[radio_df["F_kHz"] == selected_freq]


if radio_df.empty or gnss_df.empty:
    st.warning("Nicht genügend Daten vorhanden.")
    st.stop()

radio_df["timeStamp"] = pd.to_datetime(radio_df["timeStamp"])
gnss_df["timeStamp"] = pd.to_datetime(gnss_df["timeStamp"])

# Referenzpunkt definieren
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

if len(sorted_sources) >= 2:
    src1, src2 = sorted_sources[0], sorted_sources[1]
    start1, start2 = start_times[src1], start_times[src2]
    fahrt1_df = radio_df[(radio_df["source"] == src1) & (radio_df["timeStamp"] >= start1) & (radio_df["timeStamp"] < start2)].copy()
    fahrt2_df = radio_df[(radio_df["source"] == src2) & (radio_df["timeStamp"] >= start2)].copy()
elif len(sorted_sources) == 1:
    src1 = sorted_sources[0]
    start1 = start_times[src1]
    fahrt1_df = radio_df[(radio_df["source"] == src1) & (radio_df["timeStamp"] >= start1)].copy()
    fahrt2_df = pd.DataFrame()
else:
    st.warning("Keine gültigen Fahrten vorhanden.")
    st.stop()

fahrt1_df["time_rel"] = (fahrt1_df["timeStamp"] - start1).dt.total_seconds()
if not fahrt2_df.empty:
    fahrt2_df["time_rel"] = (fahrt2_df["timeStamp"] - start2).dt.total_seconds()

# ---------------------------------------------
# 🧭 Tabs: Diagramm & Karte
# ---------------------------------------------
tab1, tab2 = st.tabs(["📊 Vergleichsdiagramm", "🗺️ GNSS-Karte"])

# ---------------------------------------------
# 📊 Diagramm
# ---------------------------------------------
with tab1:
    st.header("📊 Vergleichsdiagramm")

    selected_metric = "TL" if radio_mode == "DAB" else "FS"
    y_label = "Tuner Level (dBm)" if selected_metric == "TL" else "Field Strength (dBμV)"

    with st.expander("⚙️ Anzeigeoptionen"):
        resample = st.selectbox("🕒 Zeitintervall", ["Original", "1s", "5s", "10s"], index=2)
        show_points = st.checkbox("🔵 Punkte anzeigen", value=True)
        connect_points = st.checkbox("📈 Linie", value=True)
        show_avg = st.checkbox("➕ Durchschnitt", value=False)
        show_trend = st.checkbox("📉 Tendenzlinie", value=False)
        show_reference = st.checkbox("🎯 Referenzbereich", value=True)

    chart_data = []
    for df, src in zip([fahrt1_df, fahrt2_df], [src1, src2] if not fahrt2_df.empty else [src1]):
        if df.empty:
            continue
        sub = df.set_index("timeStamp")[[selected_metric, "time_rel"]]
        if resample != "Original":
            sub = sub.resample(resample).mean().dropna()
        sub["source"] = src
        sub.reset_index(inplace=True)
        chart_data.append(sub)

    if not chart_data:
        st.warning("Keine Daten für Diagramm vorhanden.")
    else:
        combined_df = pd.concat(chart_data)
        x_axis = alt.X("time_rel:Q", title="Zeit seit Referenzpunkt [s]")
        color_scale = alt.Color("source:N", title="Fahrt")
        layers = []

        if show_reference:
            if radio_mode == "DAB":
                ref_areas = [
                    {"name": "Sehr gut", "start": -40, "end": 40, "color": "#b0f2b4"},
                    {"name": "Gut", "start": -60, "end": -40, "color": "#d9f2b0"},
                    {"name": "Mittel", "start": -80, "end": -60, "color": "#fff7b0"},
                    {"name": "Schlecht", "start": -100, "end": -80, "color": "#f2b0b0"}
                ]
            else:
                ref_areas = [
                    {"name": "Sehr gut", "start": 60, "end": 100, "color": "#b0f2b4"},
                    {"name": "Gut", "start": 40, "end": 60, "color": "#d9f2b0"},
                    {"name": "Mittel", "start": 20, "end": 40, "color": "#fff7b0"},
                    {"name": "Schlecht", "start": -20, "end": 20, "color": "#f2b0b0"}
                ]
            min_x = combined_df["time_rel"].min()
            max_x = combined_df["time_rel"].max()
            for area in ref_areas:
                bg_df = pd.DataFrame({
                    "x_start": [min_x],
                    "x_end": [max_x],
                    "y_start": [area["start"]],
                    "y_end": [area["end"]]
                })
                ref = alt.Chart(bg_df).mark_rect(opacity=0.25, color=area["color"]).encode(
                    x=alt.X("x_start:Q"), x2="x_end:Q",
                    y=alt.Y("y_start:Q"), y2="y_end:Q"
                )
                layers.append(ref)

        if show_points:
            points = alt.Chart(combined_df).mark_circle(size=30).encode(
                x=x_axis,
                y=alt.Y(selected_metric, title=y_label),
                color=color_scale,
                tooltip=[
                    alt.Tooltip("timeStamp:T", title="Zeit", format="%H:%M:%S"),
                    alt.Tooltip(f"{selected_metric}:Q", title=y_label),
                    alt.Tooltip("source:N", title="Fahrt")
                ]
            )
            layers.append(points)

        if connect_points:
            lines = alt.Chart(combined_df).mark_line().encode(
                x=x_axis,
                y=alt.Y(selected_metric, title=y_label),
                color=color_scale
            )
            layers.append(lines)

        if show_avg:
            for src in combined_df["source"].unique():
                mean_val = combined_df[combined_df["source"] == src][selected_metric].mean()
                rule = alt.Chart(pd.DataFrame({"y": [mean_val]})).mark_rule(strokeDash=[4, 2], color="gray").encode(y="y")
                layers.append(rule)

        if show_trend:
            for src in combined_df["source"].unique():
                trend_data = combined_df[combined_df["source"] == src]
                trend = alt.Chart(trend_data).transform_loess(
                    "time_rel", selected_metric, bandwidth=0.3
                ).mark_line(strokeDash=[2, 1]).encode(
                    x=x_axis,
                    y=alt.Y(selected_metric, title=y_label),
                    color=alt.Color("source:N", legend=None)
                )
                layers.append(trend)

        st.altair_chart(alt.layer(*layers).interactive(), use_container_width=True)

# ---------------------------------------------
# 🗺️ Karte
# ---------------------------------------------
with tab2:
    st.header("🗺️ GNSS-Karte")

    gnss_df = gnss_df[gnss_df["source"].isin(sorted_sources)].copy()
    radio_df = radio_df[radio_df["source"].isin(sorted_sources)].copy()

    def color_by_metric(val, is_dab):
        if pd.isna(val): return [255, 255, 255]
        if is_dab:
            return [0, 180, 0] if val > -40 else [160, 220, 100] if val > -60 else [255, 220, 0] if val > -80 else [255, 70, 70]
        else:
            return [0, 180, 0] if val > 60 else [160, 220, 100] if val > 40 else [255, 220, 0] if val > 20 else [255, 70, 70]

    def assign_colors(df, radio_df, col, is_dab):
        df = df.sort_values("timeStamp").reset_index(drop=True)
        vals, colors = [], []
        for idx in range(len(df)):
            if idx == 0:
                vals.append(None)
                colors.append([255, 255, 255])
                continue
            subset = radio_df[
                (radio_df["source"] == df.loc[idx, "source"]) &
                (radio_df["timeStamp"] > df.loc[idx - 1, "timeStamp"]) &
                (radio_df["timeStamp"] <= df.loc[idx, "timeStamp"])
            ]
            val = subset[col].mean() if not subset.empty else None
            vals.append(val)
            colors.append(color_by_metric(val, is_dab))
        df[col] = vals
        df["color"] = colors
        return df

    gnss_df["timeStr"] = gnss_df["timeStamp"].dt.strftime("%H:%M:%S")

    metric = "TL" if radio_mode == "DAB" else "FS"
    gnss_df = assign_colors(gnss_df, radio_df, metric, radio_mode == "DAB")

    mid_lat, mid_lon = gnss_df["lat"].mean(), gnss_df["lon"].mean()

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=gnss_df,
        get_position="[lon, lat]",
        get_radius=6,
        get_fill_color="color",
        pickable=True
    )

    st.pydeck_chart(pdk.Deck(
        layers=[layer],
        initial_view_state=pdk.ViewState(latitude=mid_lat, longitude=mid_lon, zoom=14),
        map_style="mapbox://styles/mapbox/satellite-v9",
        tooltip={"html": f"<b>Zeit:</b> {{timeStr}}<br/><b>{metric}:</b> {{{metric}}}", "style": {"color": "black"}}
    ))

    with st.expander("📋 GNSS-Tabelle anzeigen"):
        st.dataframe(gnss_df)
