import streamlit as st

st.set_page_config(page_title="Radio Trace Analyzer", layout="centered")

st.title("📡 Radio Trace Analyzer")
st.markdown("Willkommen! Bitte lade deine JSON-Dateien hoch, um mit der Analyse zu beginnen.")

# Initialisieren
if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = []

# Uploadfeld
uploaded = st.file_uploader("📤 JSON-Dateien hochladen", type="json", accept_multiple_files=True)

# Datei zur Session hinzufügen
if uploaded:
    for file in uploaded:
        if file.name not in [f.name for f in st.session_state.uploaded_files]:
            st.session_state.uploaded_files.append(file)

# Liste der aktuellen Uploads
if st.session_state.uploaded_files:
    st.markdown("### 📁 Hochgeladene Dateien:")
    for file in st.session_state.uploaded_files:
        st.write(f"✅ {file.name}")

    # Button zur Analyse
    if st.button("🔍 Analyse starten"):
        st.switch_page("pages/Analyse.py")
else:
    st.info("Noch keine Dateien hochgeladen.")
