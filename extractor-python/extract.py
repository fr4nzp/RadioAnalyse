# extractor-python/extract.py
import json
import re

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

def process_file(input_path, output_path, progress_callback=None):
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    total = len(data)
    combined = []

    for i, entry in enumerate(data):
        msg = entry.get("msgData", "")

        # DAB
        if "MER_NXP_MOD# Qual" in msg:
            match = re.search(r"F=(\d+)kHz.*?TL=(-?\d+).*?SNR=(\d+)", msg)
            if match:
                f, tl, snr = match.groups()
                combined.append({
                    "type": "dab",
                    "timeStamp": entry.get("timeStamp", ""),
                    "F_kHz": int(f),
                    "TL": int(tl),
                    "SNR": int(snr)
                })

        # FM
        elif "T[1/0x231]" in msg:
            match = re.search(r"fq (\d+), fs (\d+), .*?snr (\d+)", msg)
            if match:
                fq, fs, snr = match.groups()
                combined.append({
                    "type": "fm",
                    "timeStamp": entry.get("timeStamp", ""),
                    "FQ_kHz": int(fq),
                    "FS": int(fs),
                    "SNR": int(snr)
                })

        # GNSS
        elif "TRK-GNSS" in msg:
            match = re.search(r"ts=([\d\.]+), pos=\(([-\d\.]+), ([-\d\.]+),.*?\), hdg=([\-\w\.]+), fix=(\d+), antenna=(\d+)", msg)
            if match:
                ts, lat, lon, hdg, fix, antenna = match.groups()
                combined.append({
                    "type": "gnss",
                    "timeStamp": entry.get("timeStamp", ""),
                    "ts": float(ts),
                    "lat": float(lat),
                    "lon": float(lon),
                    "hdg": hdg,
                    "fix": int(fix),
                    "antenna": int(antenna)
                })

        # Progress melden
        if progress_callback and i % 100 == 0:
            percent = int((i / total) * 100)
            progress_callback(percent)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(combined, f, indent=2, ensure_ascii=False)

    # 100 % sicherstellen am Ende
    if progress_callback:
        progress_callback(100)
