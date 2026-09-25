"""Two-window Tk desktop used for the real X11 focus-contention smoke."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk


def run(state_path: Path) -> None:
    state_path.write_text(json.dumps({"Document": "", "Chat": ""}), encoding="utf-8")
    document = tk.Tk()
    document.title("Document")
    document.geometry("420x220+10+10")
    document.configure(padx=18, pady=16)
    ttk.Label(document, text="Document", font=("Sans", 16, "bold")).pack(anchor="w")
    doc_value = tk.StringVar()
    doc_entry = ttk.Entry(document, textvariable=doc_value, width=42)
    doc_entry.pack(anchor="w", pady=16)
    ttk.Label(document, text="Press Enter to save this document.").pack(anchor="w")

    chat = tk.Toplevel(document)
    chat.title("Chat")
    chat.geometry("420x220+470+10")
    chat.configure(padx=18, pady=16)
    ttk.Label(chat, text="Chat", font=("Sans", 16, "bold")).pack(anchor="w")
    chat_value = tk.StringVar()
    chat_entry = ttk.Entry(chat, textvariable=chat_value, width=42)
    chat_entry.pack(anchor="w", pady=16)
    ttk.Label(chat, text="Press Enter to send this note.").pack(anchor="w")

    def save_doc(_event=None):
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["Document"] = doc_value.get()
        state_path.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")

    def save_chat(_event=None):
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["Chat"] = chat_value.get()
        state_path.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")

    doc_entry.bind("<Return>", save_doc)
    chat_entry.bind("<Return>", save_chat)
    document.update_idletasks()
    chat.update_idletasks()
    doc_entry.focus_force()
    document.mainloop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", type=Path, default=Path("/workspace/focus_state.json"))
    run(parser.parse_args().state)
