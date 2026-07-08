"""Tk GUI front-ends for the ratings engine.

Top of the dependency stack: imports the engine (``rating``) and file writers
(``io``). Nothing in the engine imports this module. The ``pipeline`` module
subclasses ``App`` / ``SimulationApp`` to wire in the full-history replay.
"""

from datetime import datetime
import sys
import textwrap
import tkinter as tk
from tkinter import filedialog, ttk

from coco_ratings.io import CSVResultWriter
from coco_ratings.rating import Tournament


class File:
    def __init__(self, parent, name, status, save_as=False):
        self.name = name
        self.status = status
        self.save_as = save_as
        self.label = ttk.Label(parent, text=f"{name}:")
        self.file = None
        self.file_label = ttk.Label(parent, text="")
        b = "Save as" if self.save_as else "Open"
        self.button = ttk.Button(parent, text=b)
        self.button["command"] = self.select_file
        self.set_file_label()

    def set_file_label(self):
        if self.file:
            text = self.file
            style = "BW.TLabel"
        else:
            text = "[No file selected]"
            style = "GW.TLabel"
        self.file_label.configure(text=text, style=style)

    def select_file(self):
        filetypes = (("csv files", "*.?sv"), ("All files", "*.*"))
        if self.save_as:
            filename = filedialog.asksaveasfilename(
                title="Save new ratings", filetypes=filetypes
            )
        else:
            filename = filedialog.askopenfilename(
                title=f"Open {self.name} file", filetypes=filetypes
            )
        self.file = filename
        self.set_file_label()
        self.status.set_status(f"Set {self.name} file")


class FilesWidget(ttk.Frame):
    def __init__(self, container, status):
        super().__init__(container)
        self.files = {}
        self.status = status
        self._init_widgets()

    def get_files(self):
        return [self.files[x].file for x in ("Ratings", "Results", "New results")]

    def _add_file(self, name, row, save_as=False):
        f = File(self, name, self.status, save_as)
        self.files[name] = f
        f.label.grid(column=0, row=row, sticky=tk.EW, padx=5, pady=1, ipady=5)
        f.file_label.grid(column=1, row=row, sticky=tk.EW, padx=5, pady=1, ipady=5)
        f.button.grid(column=2, row=row, sticky=tk.EW, padx=5, pady=1, ipady=5)

    def _init_widgets(self):
        self._add_file("Ratings", 0)
        self._add_file("Results", 1)
        self._add_file("New results", 2, save_as=True)
        self.grid(padx=10, pady=0, sticky=tk.NSEW)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("COCO Ratings Calculator")
        self.geometry("1200x800")
        self.init_style()
        self.frame = ttk.Frame(self)
        self._init_widgets()

    def _init_widgets(self):
        label = self._instructions()
        self.output = ttk.Label(self.frame)
        self.files = FilesWidget(self.frame, status=self)
        buttonbox = ttk.Frame(self.frame)
        button1 = ttk.Button(buttonbox, text="Calculate new ratings")
        button1["command"] = self.calculate_ratings
        button2 = ttk.Button(buttonbox, text="Recalculate latest tournament")
        button2["command"] = self.recalculate_ratings
        # layout widgets
        label.grid(row=0)
        self.files.grid(row=1, pady=10, sticky=tk.EW)
        self.files.grid_columnconfigure(1, weight=1)
        button1.grid(row=0, column=0, padx=10, pady=10)
        button2.grid(row=0, column=1, padx=10, pady=10)
        buttonbox.grid(row=2, pady=20)
        self.output.grid(row=3, pady=20, columnspan=3)
        self.frame.grid(ipadx=10, padx=2, pady=2, sticky=tk.NSEW)

    def _instructions(self):
        text = textwrap.dedent("""
        Instructions:

        * Export a ratings file and a results file from a spreadsheet in CSV format
        * Load both files into the fields below.
        * Select a file to save the new ratings to.
        * Click "Calculate Ratings"

        Expected csv columns:
          rating: Name, Rating
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

    def calculate_ratings(self):
        rating_file, result_file, outfile = self.files.get_files()
        if not (rating_file and result_file and outfile):
            self.set_status("Some filenames are not set")
            return
        name = "Tournament name"
        tdate = datetime.today()
        t = Tournament(rating_file, result_file, name, tdate)
        t.calc_ratings()
        CSVResultWriter().write_file(outfile, t)
        self.set_status(f"Wrote new ratings to {outfile}")

    def recalculate_ratings(self):
        # implemented in all_ratings.py
        pass


class SimulationApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("COCO Ratings Simulator")
        self.geometry("1200x800")
        self.init_style()
        self.frame = ttk.Frame(self)
        self._init_widgets()

    def _init_widgets(self):
        label = self._instructions()
        self.output = ttk.Label(self.frame)
        self.beta_input = tk.StringVar()
        inputbox = ttk.Frame(self.frame)
        beta_label = ttk.Label(inputbox, text="beta = ")
        self.entry = ttk.Entry(inputbox, textvariable=self.beta_input)
        buttonbox = ttk.Frame(self.frame)
        button1 = ttk.Button(buttonbox, text="Run simulation")
        button1["command"] = self.run_simulation
        button2 = ttk.Button(buttonbox, text="Quit")
        button2["command"] = self.quit
        # layout widgets
        label.grid(row=0)
        beta_label.grid(row=0, column=0)
        self.entry.grid(row=0, column=1, columnspan=2)
        inputbox.grid(row=1, pady=10, sticky=tk.EW)
        button1.grid(row=0, column=0, padx=10, pady=10)
        button2.grid(row=0, column=1, padx=10, pady=10)
        buttonbox.grid(row=2, pady=20)
        self.output.grid(row=3, pady=20, columnspan=3)
        self.frame.grid(ipadx=10, padx=2, pady=2, sticky=tk.NSEW)

    def _instructions(self):
        text = textwrap.dedent("""
        Instructions:

        * Pick a value for beta (default = 5)
        * Click on "Run Simulation"

        beta is rating points difference per point of expected spread
        If, for instance, beta = 5, it means that if a player is rated 100
        points above another player, the spread in games played between the two
        players should on average be 100 / 5 = 20 points in favour of the first
        player. i.e. the lower beta is, the more the higher-rated player is
        expected to win by.

        The result will be written to a csv file which can be imported into
        a spreadsheet.
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

    def quit(self):
        sys.exit(0)

    def run_simulation(self):
        # implemented in all_ratings.py
        pass


def run_gui():
    w = App()
    w.mainloop()
