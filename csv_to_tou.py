from datetime import datetime
import sys
import textwrap

import tkinter as tk
from tkinter import ttk, filedialog

from rating import File, Tournament, TouResultWriter


class FilesWidget(ttk.Frame):
    def __init__(self, container, status):
        super().__init__(container)
        self.files = {}
        self.status = status
        self._init_widgets()

    def get_files(self):
        return [self.files[x].file for x in ("CSV Results File", "TOU File")]

    def _add_file(self, name, row, save_as=False):
        f = File(self, name, self.status, save_as)
        self.files[name] = f
        opts = {"padx": 5, "pady": 1, "ipady": 5}
        f.label.grid(column=0, row=row, sticky=tk.EW, **opts)
        f.file_label.grid(column=1, row=row, sticky=tk.EW, **opts)
        f.button.grid(column=2, row=row, sticky=tk.EW, **opts)

    def _init_widgets(self):
        self._add_file("CSV Results File", 0)
        self._add_file("TOU File", 1, save_as=True)
        self.grid(padx=10, pady=0, sticky=tk.NSEW)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CSV to TOU Results Converter")
        self.geometry("1200x800")
        self.init_style()
        self.frame = ttk.Frame(self)
        self._init_widgets()

    def _init_widgets(self):
        label = self._instructions()
        self.output = ttk.Label(self.frame)
        self.files = FilesWidget(self.frame, status=self)
        button = ttk.Button(self.frame, text="Convert")
        button["command"] = self.convert
        # layout widgets
        label.grid(row=0)
        self.files.grid(row=1, pady=10, sticky=tk.EW)
        self.files.grid_columnconfigure(1, weight=1)
        button.grid(row=2, pady=20)
        self.output.grid(row=3, pady=20, columnspan=3)
        self.frame.grid(ipadx=10, padx=2, pady=2, sticky=tk.NSEW)

    def _instructions(self):
        text = textwrap.dedent("""
        Instructions:

        * Export a results file from a spreadsheet in CSV format
        * Select a file to save the TOU formatted results to.
        * Click "Convert"

        Expected csv columns:
          results: Submitted On, Round, Winner, Score, Opponent, Score

        Keep the csv header row, the script skips the first row.
        """)
        ret = tk.Text(self.frame, width=80, height=14)
        ret.insert("end", text)
        ret.config(state="disabled")
        return ret

    def init_style(self):
        style = ttk.Style()
        style.configure("BW.TLabel", foreground="black", background="white")
        style.configure("GW.TLabel", foreground="grey", background="white")
        return style

    def set_status(self, text):
        self.output.configure(text=text)

    def convert(self):
        result_file, outfile = self.files.get_files()
        if not (result_file and outfile):
            self.set_status("Some filenames are not set")
            return
        if not outfile.lower().endswith(".tou"):
            self.set_status("Output file does not have extension .tou")
            return
        convert_csv(result_file, outfile)
        self.set_status(f"Wrote results to {outfile}")


def convert_csv(result_file, outfile):
    name = "Tournament name"
    tdate = datetime.today()
    t = Tournament(None, result_file, name, tdate)
    TouResultWriter().write_file(outfile, t)


def run_gui():
    w = App()
    w.mainloop()


def run_cli():
    if len(sys.argv) != 3:
        print("Usage:")
        print(f"  {sys.argv[0]} input-file.csv output-file.tou")
        sys.exit(1)

    _, infile, outfile = sys.argv
    convert_csv(infile, outfile)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_cli()
    else:
        run_gui()
