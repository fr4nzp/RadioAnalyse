import json

with open("assets/gekürzt.json", "r", encoding="utf-8") as infile:
    data = json.load(infile)

fm_messages = [
    entry for entry in data
    if "msgData" in entry and ("T[3/0x232]" in entry["msgData"] or "T[4/0x233]" in entry["msgData"])
]

with open("assets/fm.json", "w", encoding="utf-8") as outfile:
    json.dump(fm_messages, outfile, indent=2, ensure_ascii=False)

print(f"{len(fm_messages)} FM-Nachrichten gespeichert in fm.json")
