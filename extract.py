# extract.py
import json
import re
import os
from datetime import datetime

def extract_dab(data):
    dab_entries = []
    for entry in data:
        msg = entry.get("msgData", "")
        if "LRID0x161" in msg:  # Nur noch 161
            match = re.search(r"F=(\d+)kHz.*?RSSI=(-?\d+).*?SNR=(\d+)", msg)
            if match:
                f, rssi, snr = match.groups()
                dab_entries.append({
                    "type": "dab",
                    "timeStamp": entry.get("timeStamp", ""),
                    "F_kHz": int(f),
                    "RSSI": int(rssi),
                    "SNR": int(snr)
                })
    return dab_entries

def extract_fm(data):
    fm_entries = []
    for entry in data:
        msg = entry.get("msgData", "")
        if "T[1/0x231]" in msg:  # Nur noch dieser FM-Tuner erlaubt
            match = re.search(r"fq (\d+), fs (\d+), .*?snr (\d+)", msg)
            if match:
                fq, fs, snr = match.groups()
                fm_entries.append({
                    "type": "fm",
                    "timeStamp": entry.get("timeStamp", ""),
                    "FQ_kHz": int(fq),
                    "FS": int(fs),
                    "SNR": int(snr)
                })
    return fm_entries

def extract_gnss(data):
    gnss_entries = []
    for entry in data:
        msg = entry.get("msgData", "")
        if "TRK-GNSS" in msg:
            match = re.search(r"ts=([\d\.]+), pos=\(([-\d\.]+), ([-\d\.]+),.*?\), hdg=([\-\w\.]+), fix=(\d+), antenna=(\d+)", msg)
            if match:
                ts, lat, lon, hdg, fix, antenna = match.groups()
                gnss_entries.append({
                    "type": "gnss",
                    "timeStamp": entry.get("timeStamp", ""),
                    "ts": float(ts),
                    "lat": float(lat),
                    "lon": float(lon),
                    "hdg": hdg,
                    "fix": int(fix),
                    "antenna": int(antenna)
                })
    return gnss_entries

def main(input_path, output_prefix):
    if not os.path.exists(input_path):
        print(f"❌ Datei nicht gefunden: {input_path}")
        return

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    dab_data = extract_dab(data)
    fm_data = extract_fm(data)
    gnss_data = extract_gnss(data)

    dab_combined = dab_data + gnss_data
    fm_combined = fm_data + gnss_data

    with open(f"assets/{output_prefix}dab+gnss.json", "w", encoding="utf-8") as f:
        json.dump(dab_combined, f, indent=2, ensure_ascii=False)

    with open(f"assets/{output_prefix}fm+gnss.json", "w", encoding="utf-8") as f:
        json.dump(fm_combined, f, indent=2, ensure_ascii=False)

    print(f"✅ {len(dab_data)} DAB + {len(gnss_data)} GNSS → gespeichert in assets/{output_prefix}dab+gnss.json")
    print(f"✅ {len(fm_data)} FM + {len(gnss_data)} GNSS → gespeichert in assets/{output_prefix}fm+gnss.json")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, default="traces/MacanFahrtTest.json", help="Pfad zur Trace-Datei")
    parser.add_argument("--output", type=str, default="", help="Optionaler Präfix für die Output-Dateien")
    args = parser.parse_args()

    main(args.input, args.output)
