"""Convert a CSV results file to AUPAIR's .tou format.

Runs from a plain checkout with nothing but Python installed — no venv, no
install step, no third-party packages. Double-click it (or run with no
arguments) for the GUI; pass an input and output file for the command line.

A .tou file carries the tournament's name and date in its header line, which a
results CSV does not, so both have to be supplied. If the input file is one of
this repo's own results files they are looked up in data/tournaments.csv as a
convenience — but the script is just as often pointed at a one-off export that
was never added there, so the lookup is only ever a default to be overridden,
never a requirement.
"""

import argparse
from datetime import datetime
from pathlib import Path
import sys
import textwrap

# Make the checkout importable without installing it: coco_ratings lives under
# src/ (a "src layout"), which is not on the import path by default. Must come
# before the coco_ratings imports below.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import tkinter as tk  # noqa: E402
from tkinter import ttk  # noqa: E402

from coco_ratings.gui import File  # noqa: E402
from coco_ratings.io import TouResultWriter  # noqa: E402
from coco_ratings.rating import Tournament  # noqa: E402

DATE_FORMAT = "%Y-%m-%d"


def parse_date(text):
    """Parse a yyyy-mm-dd date, raising ValueError with a readable message."""
    try:
        return datetime.strptime(text.strip(), DATE_FORMAT)
    except ValueError:
        raise ValueError(f"Cannot parse date {text!r} — expected yyyy-mm-dd") from None


def lookup_tournament(result_file):
    """Best-effort (name, date) for a results file, from data/tournaments.csv.

    Returns (None, None) whenever the file is not one of this repo's — a
    differently named export, a file from elsewhere, or a checkout without the
    data directory. Callers must cope with that; the details are always
    overridable and never assumed to be available.
    """
    stem = Path(result_file).name
    for suffix in ("-results.csv", "-results.tsv"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    else:
        return None, None

    try:
        from coco_ratings.tournaments import TournamentDB

        entries = TournamentDB.read_csv().tournaments
    except (OSError, ValueError, TypeError):
        return None, None

    for entry in entries:
        if entry.filename == stem:
            # Divisions of one event share a fancy name, so keep them distinct.
            name = " ".join(x for x in (entry.fancy_name, entry.division) if x.strip())
            try:
                return name, parse_date(entry.date)
            except ValueError:
                return name, None
    return None, None


class FilesWidget(ttk.Frame):
    def __init__(self, container, status, on_results_selected=None):
        super().__init__(container)
        self.files = {}
        self.status = status
        self.on_results_selected = on_results_selected
        self._init_widgets()

    def get_files(self):
        return [self.files[x].file for x in ("CSV Results File", "TOU File")]

    def _add_file(self, name, row, save_as=False, on_select=None):
        f = File(self, name, self.status, save_as)
        self.files[name] = f
        if on_select is not None:
            # File has no selection hook, so wrap its button command rather
            # than modifying the shared widget in coco_ratings.gui.
            def choose(file=f, callback=on_select):
                file.select_file()
                if file.file:
                    callback(file.file)

            f.button["command"] = choose
        f.label.grid(column=0, row=row, sticky=tk.EW, padx=5, pady=1, ipady=5)
        f.file_label.grid(column=1, row=row, sticky=tk.EW, padx=5, pady=1, ipady=5)
        f.button.grid(column=2, row=row, sticky=tk.EW, padx=5, pady=1, ipady=5)

    def _init_widgets(self):
        self._add_file("CSV Results File", 0, on_select=self.on_results_selected)
        self._add_file("TOU File", 1, save_as=True)
        self.grid(padx=10, pady=0, sticky=tk.NSEW)


class DetailsWidget(ttk.Frame):
    """Tournament name and date — the two things a CSV cannot tell us."""

    def __init__(self, container):
        super().__init__(container)
        self.name = tk.StringVar()
        self.date = tk.StringVar()
        self._init_widgets()

    def _init_widgets(self):
        rows = [("Tournament name", self.name), ("Date (yyyy-mm-dd)", self.date)]
        for row, (label, var) in enumerate(rows):
            ttk.Label(self, text=f"{label}:").grid(
                column=0, row=row, sticky=tk.EW, padx=5, pady=1, ipady=5
            )
            ttk.Entry(self, textvariable=var, width=40).grid(
                column=1, row=row, sticky=tk.EW, padx=5, pady=1, ipady=2
            )
        self.grid(padx=10, pady=0, sticky=tk.NSEW)

    def prefill(self, name, date):
        """Fill in looked-up details, without overwriting anything typed."""
        if name and not self.name.get().strip():
            self.name.set(name)
        if date and not self.date.get().strip():
            self.date.set(date.strftime(DATE_FORMAT))

    def get_details(self):
        """Return (name, date), raising ValueError if either is unusable."""
        name = self.name.get().strip()
        if not name:
            raise ValueError("Tournament name is not set")
        date = self.date.get().strip()
        if not date:
            raise ValueError("Date is not set")
        return name, parse_date(date)


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
        self.details = DetailsWidget(self.frame)
        self.files = FilesWidget(
            self.frame, status=self, on_results_selected=self._results_selected
        )
        button = ttk.Button(self.frame, text="Convert")
        button["command"] = self.convert
        # layout widgets
        label.grid(row=0)
        self.files.grid(row=1, pady=10, sticky=tk.EW)
        self.files.grid_columnconfigure(1, weight=1)
        self.details.grid(row=2, pady=0, sticky=tk.EW)
        self.details.grid_columnconfigure(1, weight=1)
        button.grid(row=3, pady=20)
        self.output.grid(row=4, pady=20, columnspan=3)
        self.frame.grid(ipadx=10, padx=2, pady=2, sticky=tk.NSEW)

    def _results_selected(self, result_file):
        """Offer the tournament details if we happen to know this file."""
        name, date = lookup_tournament(result_file)
        self.details.prefill(name, date)
        if name:
            self.set_status(f"Found tournament details for {Path(result_file).name}")

    def _instructions(self):
        text = textwrap.dedent("""
        Instructions:

        * Export a results file from a spreadsheet in CSV format
        * Select a file to save the TOU formatted results to.
        * Enter the tournament name and date. A .tou file records both, and a
          results CSV does not, so they cannot be guessed from the results. For
          this repo's own results files they are filled in for you; check them.
        * Click "Convert"

        Expected csv columns:
          results: Submitted On, Round, Winner, Score, Opponent, Score

        Keep the csv header row, the script skips the first row.
        """)
        ret = tk.Text(self.frame, width=80, height=16)
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
        try:
            name, tdate = self.details.get_details()
        except ValueError as e:
            self.set_status(str(e))
            return
        convert_csv(result_file, outfile, name, tdate)
        self.set_status(f"Wrote {name} ({tdate.strftime(DATE_FORMAT)}) to {outfile}")


def convert_csv(result_file, outfile, name, tdate):
    """Write result_file out as .tou, headed with the given name and date."""
    t = Tournament(None, result_file, name, tdate)
    TouResultWriter().write_file(outfile, t)


def run_gui():
    w = App()
    w.mainloop()


def run_cli(argv=None):
    parser = argparse.ArgumentParser(
        prog=Path(sys.argv[0]).name,
        description="Convert a CSV results file to AUPAIR's .tou format.",
        epilog=(
            "A .tou file records the tournament name and date; a results CSV "
            "does not. Supply them with --name and --date. For this repo's own "
            "results files they default to the entry in data/tournaments.csv. "
            "Run with no arguments for the GUI."
        ),
    )
    parser.add_argument("infile", metavar="input-file.csv")
    parser.add_argument("outfile", metavar="output-file.tou")
    parser.add_argument("--name", help="Tournament name")
    parser.add_argument("--date", help="Tournament date (yyyy-mm-dd)")
    args = parser.parse_args(argv)

    if not args.outfile.lower().endswith(".tou"):
        parser.error(f"output file {args.outfile!r} does not have extension .tou")

    # Anything not given falls back to the repo's own tournament list, which
    # only knows about files that live in results/.
    name, tdate = (args.name, None)
    if not (args.name and args.date):
        found_name, found_date = lookup_tournament(args.infile)
        name = args.name or found_name
        tdate = found_date
    if args.date:
        try:
            tdate = parse_date(args.date)
        except ValueError as e:
            parser.error(str(e))

    if not name or tdate is None:
        missing = [f for f, v in (("--name", name), ("--date", tdate)) if not v]
        parser.error(
            f"{' and '.join(missing)} required: {Path(args.infile).name} is not "
            "in data/tournaments.csv, so its details cannot be looked up"
        )

    convert_csv(args.infile, args.outfile, name, tdate)
    print(f"Wrote {name} ({tdate.strftime(DATE_FORMAT)}) to {args.outfile}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_cli()
    else:
        run_gui()
