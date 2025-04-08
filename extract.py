# extract.py
import json
import re
import os

def extract_dab(entry):
    msg = entry.get("msgData", "")
    if "LRID0x161" in msg:
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

def extract_fm(entry):
    msg = entry.get("msgData", "")
    if "T[1/0x231]" in msg:
        match = re.search(r"fq (\d+), fs (\d+), .*?snr (\d+)", msg)
        if match:
            fq, fs, snr = match.groups()
            return {
                "type": "fm",
                "timeStamp": entry.get("timeStamp", ""),
                "FQ_kHz": int(fq),
                "FS": int(fs),
                "SNR": int(snr)
            }
    return None

def extract_gnss(entry):
    msg = entry.get("msgData", "")
    if "TRK-GNSS" in msg:
        match = re.search(r"ts=([\d\.]+), pos=\(([-\d\.]+), ([-\d\.]+),.*?\), hdg=([\-\w\.]+), fix=(\d+), antenna=(\d+)", msg)
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

def process_file(filepath, output_dir):
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    result = []
    for entry in data:
        for extractor in [extract_dab, extract_fm, extract_gnss]:
            parsed = extractor(entry)
            if parsed:
                result.append(parsed)

    filename = os.path.splitext(os.path.basename(filepath))[0]
    out_path = os.path.join(output_dir, f"{filename}.parsed.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"✅ {filename}.parsed.json – {len(result)} Einträge")

def main():
    trace_dir = "traces"
    output_dir = "data"
    os.makedirs(output_dir, exist_ok=True)

    for file in os.listdir(trace_dir):
        if file.endswith(".json"):
            process_file(os.path.join(trace_dir, file), output_dir)

if __name__ == "__main__":
    main()
