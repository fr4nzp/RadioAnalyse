import streamlit as st

st.set_page_config(page_title="📥 Downloads", layout="centered")
st.title("📥 Extraktions-Tools herunterladen")

st.markdown("""
Hier findest du alle verfügbaren ZIP-Archive zur lokalen Extraktion von Rohdaten.
Diese Tools helfen dir, große JSON-Dateien außerhalb der App zu verarbeiten.
""")

# Nur ein ZIP vorerst
with open("extractor-python.zip", "rb") as f:
    st.download_button(
        label="📦 Lokalen Extractor herunterladen (.zip)",
        data=f,
        file_name="RadioTraceExtractor_Python.zip",
        mime="application/zip"
    )

st.info("""
ℹ️ Der lokale Extractor kann über `extract_gui.py` gestartet werden und benötigt Python 3.
""")
