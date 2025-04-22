import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import threading
from extract import process_file

def select_file():
    path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
    if path:
        input_path.set(path)
        output_path.set("")

def select_output():
    folder = filedialog.askdirectory()
    if folder and input_path.get():
        base = os.path.splitext(os.path.basename(input_path.get()))[0]
        generated_name = base + "_extracted.json"
        output_path.set(os.path.join(folder, generated_name))
    elif not input_path.get():
        messagebox.showwarning("Hinweis", "Bitte zuerst eine Quelldatei auswählen.")

def update_progress(value):
    progress_var.set(value)
    percent_label.config(text=f"{value} %")

def run_conversion():
    try:
        convert_button.config(state="disabled")
        progressbar["value"] = 0
        update_progress(0)

        process_file(
            input_path.get(),
            output_path.get(),
            progress_callback=update_progress
        )

        messagebox.showinfo("Fertig", f"Datei wurde erfolgreich gespeichert als:\n{output_path.get()}")
    except Exception as e:
        messagebox.showerror("Fehler", f"Fehler beim Verarbeiten:\n{e}")
    finally:
        convert_button.config(state="normal")

def run_thread():
    thread = threading.Thread(target=run_conversion)
    thread.start()

# GUI
root = tk.Tk()
root.title("Radio Trace Extractor")
root.geometry("500x380")

input_path = tk.StringVar()
output_path = tk.StringVar()
progress_var = tk.IntVar(value=0)

tk.Label(root, text="Quelldatei (JSON):").pack(pady=5)
tk.Entry(root, textvariable=input_path, width=60).pack()
tk.Button(root, text="Durchsuchen...", command=select_file).pack()

tk.Label(root, text="Zielordner:").pack(pady=5)
tk.Button(root, text="Zielordner wählen...", command=select_output).pack()
tk.Label(root, textvariable=output_path, wraplength=480, fg="gray").pack(pady=(5, 10))

progressbar = ttk.Progressbar(root, variable=progress_var, maximum=100, length=400)
progressbar.pack(pady=(5, 0))
percent_label = tk.Label(root, text="0 %", fg="gray")
percent_label.pack()

convert_button = tk.Button(root, text="Verarbeiten", command=run_thread, bg="green", fg="white", padx=10, pady=5)
convert_button.pack(pady=15)

root.mainloop()
