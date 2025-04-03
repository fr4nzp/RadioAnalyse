# parse_and_extract.py
import json
import os
import argparse
import re

def extract_dab(entry):
    msg = entry.get("msgData", "")
    if "LRID0x161" in msg or "LRID0x162" in msg:
        match = re.search(r"F=(\d+)kHz.*?RSSI=(-?\d+).*?SNR=(\d+)", msg)
        if match:
            f, rssi, snr = match.groups()
            return {
                "type": "dab",
                "timeStamp": entry.get("timeStamp", ""),
                "F_kHz": int(f),
                "RSSI": int(rssi),
                "SNR": int(snr)
            }
    return None

def extract_gnss(entry):
    msg = entry.get("msgData", "")
    if "TRK-GNSS" in msg:
        match = re.search(
            r"ts=([\d\.]+), pos=\(([-\d\.]+), ([-\d\.]+),.*?\), hdg=([-\w\.]+), fix=(\d+), antenna=(\d+)", msg
        )
        if match:
            ts, lat, lon, hdg, fix, antenna = match.groups()
            return {
                "type": "gnss",
                "timeStamp": entry.get("timeStamp", ""),
                "ts": float(ts),
                "lat": float(lat),
                "lon": float(lon),
                "hdg": hdg,
                "fix": int(fix),
                "antenna": int(antenna)
            }
    return None

def main(input_path, output_file):
    with open(input_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    combined = []
    for entry in raw_data:
        dab = extract_dab(entry)
        if dab:
            combined.append(dab)
        gnss = extract_gnss(entry)
        if gnss:
            combined.append(gnss)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(combined, f, indent=2, ensure_ascii=False)

    print(f"✅ Extraktion abgeschlossen. {len(combined)} Einträge gespeichert in {output_file}.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Große JSON-Datei extrahieren")
    parser.add_argument("--input", default="traces/MacanFahrtTest.json", help="Pfad zur großen Trace-Datei (JSON)")
    parser.add_argument("--output", default="assets/dab+gnss.json", help="Zieldatei für kombinierten Output")
    args = parser.parse_args()

    main(args.input, args.output)