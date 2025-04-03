import json

with open("assets/gekürzt.json", "r", encoding="utf-8") as infile:
    data = json.load(infile)

dab_messages = [
    entry for entry in data
    if "msgData" in entry and ("LRID0x161" in entry["msgData"] or "LRID0x162" in entry["msgData"])
]

with open("assets/dab.json", "w", encoding="utf-8") as outfile:
    json.dump(dab_messages, outfile, indent=2, ensure_ascii=False)

print(f"{len(dab_messages)} DAB-Nachrichten gespeichert in dab.json")
