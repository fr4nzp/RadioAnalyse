import streamlit as st
import hashlib
import json

# Login-Funktion mit Hash-Vergleich
def login():
    st.title("🔐 Login")

    username = st.text_input("Benutzername")
    password = st.text_input("Passwort", type="password")

    if st.button("Einloggen"):
        try:
            with open("users.json", "r") as f:
                users = json.load(f)
        except FileNotFoundError:
            st.error("Benutzerdatei nicht gefunden.")
            return

        hashed_pw = hashlib.md5(password.encode()).hexdigest()

        if username in users and users[username] == hashed_pw:
            st.session_state["auth"] = True
            st.session_state["user"] = username
            st.success(f"Willkommen, {username}!")
            st.rerun()   
        else:
            st.error("❌ Zugangsdaten falsch.")

if "auth" not in st.session_state:
    login()
    st.stop()

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


st.markdown("## 🧰 Lokaler Extractor für große Dateien")

st.markdown("""
Dieses Tool ist für die **lokale Verarbeitung sehr großer JSON-Dateien** gedacht.

### 🧑‍💻 Anleitung:

1. Lade das ZIP herunter  
2. Entpacke es  
3. Doppelklicke auf `start.bat`  
4. Wähle deine Quelldatei und den Zielpfad  
5. Die extrahierte JSON-Datei kannst du anschließend hier hochladen

👉 Voraussetzung: **Python 3** muss installiert sein
""")

with open("extractor-python.zip", "rb") as f:
    st.download_button(
        "📥 Lokalen Extractor herunterladen (.zip)",
        f,
        file_name="RadioTraceExtractor_Python.zip"
    )
