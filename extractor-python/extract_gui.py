# extractor-python/extract_gui.py
import tkinter as tk
import os
from tkinter import filedialog, messagebox
from extract import process_file

def select_file():
    path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
    if path:
        input_path.set(path)
        # Leere das Output-Feld, falls schon vorher etwas drinstand
        output_path.set("")

def select_output():
    folder = filedialog.askdirectory()
    if folder and input_path.get():
        base = os.path.splitext(os.path.basename(input_path.get()))[0]
        generated_name = base + "_extracted.json"
        output_path.set(os.path.join(folder, generated_name))
    elif not input_path.get():
        messagebox.showwarning("Hinweis", "Bitte zuerst eine Quelldatei auswählen.")

def run():
    try:
        process_file(input_path.get(), output_path.get())
        messagebox.showinfo("Fertig", f"Datei wurde erfolgreich gespeichert als:\n{output_path.get()}")
    except Exception as e:
        messagebox.showerror("Fehler", f"Fehler beim Verarbeiten:\n{e}")

# GUI-Fenster aufbauen
root = tk.Tk()
root.title("Radio Trace Extractor")
root.geometry("500x300")

# Speicher für Pfade
input_path = tk.StringVar()
output_path = tk.StringVar()

# GUI-Elemente
tk.Label(root, text="Quelldatei (JSON):").pack(pady=5)
tk.Entry(root, textvariable=input_path, width=60).pack()
tk.Button(root, text="Durchsuchen...", command=select_file).pack()

tk.Label(root, text="Zielordner:").pack(pady=5)
tk.Button(root, text="Zielordner wählen...", command=select_output).pack()
tk.Label(root, textvariable=output_path, wraplength=480, fg="gray").pack(pady=(5, 10))

tk.Button(root, text="Verarbeiten", command=run, bg="green", fg="white", padx=10, pady=5).pack(pady=10)

root.mainloop()
