# extractor-tool/extract_gui.py
import tkinter as tk
from tkinter import filedialog, messagebox
from extract import process_file

def select_file():
    path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
    if path:
        input_path.set(path)

def select_output():
    path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")])
    if path:
        output_path.set(path)

def run():
    try:
        process_file(input_path.get(), output_path.get())
        messagebox.showinfo("Fertig", "Datei wurde erfolgreich verarbeitet!")
    except Exception as e:
        messagebox.showerror("Fehler", f"Fehler beim Verarbeiten:\n{e}")

root = tk.Tk()
root.title("Radio Trace Extractor")
root.geometry("500x250")

input_path = tk.StringVar()
output_path = tk.StringVar()

tk.Label(root, text="Quelldatei (JSON):").pack(pady=5)
tk.Entry(root, textvariable=input_path, width=60).pack()
tk.Button(root, text="Durchsuchen...", command=select_file).pack()

tk.Label(root, text="Zieldatei:").pack(pady=5)
tk.Entry(root, textvariable=output_path, width=60).pack()
tk.Button(root, text="Speichern unter...", command=select_output).pack()

tk.Button(root, text="Verarbeiten", command=run, bg="green", fg="white", padx=10, pady=5).pack(pady=10)

root.mainloop()
