# extractor-python/extract_gui.py
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import threading
from extract import process_file

def select_file():
    path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
    if path:
        input_path.set(path)
        output_path.set("")  # Reset output when input changes

def select_output():
    folder = filedialog.askdirectory()
    if folder and input_path.get():
        base = os.path.splitext(os.path.basename(input_path.get()))[0]
        generated_name = base + "_extracted.json"
        output_path.set(os.path.join(folder, generated_name))
    elif not input_path.get():
        messagebox.showwarning("Hinweis", "Bitte zuerst eine Quelldatei auswählen.")

def run_conversion():
    try:
        # Start progressbar
        progressbar.start()
        convert_button.config(state="disabled")

        process_file(input_path.get(), output_path.get())

        messagebox.showinfo("Fertig", f"Datei wurde erfolgreich gespeichert als:\n{output_path.get()}")
    except Exception as e:
        messagebox.showerror("Fehler", f"Fehler beim Verarbeiten:\n{e}")
    finally:
        # Stop progressbar
        progressbar.stop()
        convert_button.config(state="normal")

def run_thread():
    thread = threading.Thread(target=run_conversion)
    thread.start()

# GUI-Fenster aufbauen
root = tk.Tk()
root.title("Radio Trace Extractor")
root.geometry("500x340")

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

# Fortschrittsbalken
progressbar = ttk.Progressbar(root, mode="indeterminate", length=400)
progressbar.pack(pady=5)

# Verarbeiten-Button
convert_button = tk.Button(root, text="Verarbeiten", command=run_thread, bg="green", fg="white", padx=10, pady=5)
convert_button.pack(pady=10)

root.mainloop()
