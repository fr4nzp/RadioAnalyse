# extract.py
import json
import re
import os

def extract_dab(data):
    dab_entries = []
    for entry in data:
        msg = entry.get("msgData", "")
        if "MER_NXP_MOD# Qual" in msg:
            match = re.search(r"F=(\d+)kHz.*?TL=(-?\d+).*?SNR=(\d+)", msg)
            if match:
                f, tl, snr = match.groups()
                dab_entries.append({
                    "type": "dab",
                    "timeStamp": entry.get("timeStamp", ""),
                    "F_kHz": int(f),
                    "TL": int(tl),
                    "SNR": int(snr)
                })
    return dab_entries

def extract_fm(data):
    fm_entries = []
    for entry in data:
        msg = entry.get("msgData", "")
        if "T[1/0x231]" in msg:
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

def process_file(input_path, output_path):
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    combined = extract_dab(data) + extract_fm(data) + extract_gnss(data)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(combined, f, indent=2, ensure_ascii=False)

    print(f"✅ {output_path} ({len(combined)} Einträge)")

def main():
    input_folder = "traces"
    output_folder = "data"
    os.makedirs(output_folder, exist_ok=True)

    for filename in os.listdir(input_folder):
        if filename.endswith(".json"):
            input_path = os.path.join(input_folder, filename)
            output_path = os.path.join(output_folder, filename)
            process_file(input_path, output_path)

if __name__ == "__main__":
    main()
