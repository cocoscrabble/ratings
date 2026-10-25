"""The tournament list and results files are well formed.

This is the test a new tournament has to pass, and the only one it can fail:
it checks the files, not the ratings. The same checks run as
``uv run coco-rate check``. See ``coco_ratings.validate``.
"""

import tempfile
import textwrap
import unittest
from pathlib import Path

from coco_ratings.validate import check

HEADER = "Submitted On,Round,Winner,Winners Score,Opponent,Opponents Score"
NUMBERED = HEADER + ",Winner Number,Opponent Number"


class LiveCorpusTest(unittest.TestCase):
    def test_corpus_is_well_formed(self):
        problems = check()
        self.assertEqual(problems, [], "\n" + "\n".join(problems))


class ChecksTest(unittest.TestCase):
    """Each check, on a scratch corpus with one thing wrong."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "results").mkdir()
        self.write("players.csv", """\
            Name,Number
            Ann Able,1
            Bob Baker,2
            Cy Cole,3
            Di Dunn,4
        """)
        self.tournaments = [("Test Open", "t-2026", "2026-11-01")]
        self.results("t-2026", f"""\
            {HEADER}
            x,1,Ann Able,400,Bob Baker,350
            x,1,Cy Cole,420,Di Dunn,300
            x,2,Ann Able,410,Cy Cole,390
            x,2,Bob Baker,380,Di Dunn,370
        """)

    def write(self, rel, text):
        (self.root / rel).write_text(textwrap.dedent(text))

    def results(self, filename, text, ext="csv"):
        self.write(f"results/{filename}-results.{ext}", text)

    def problems(self):
        rows = ["FancyName,Division,City,Name,Tournament,Filename,Date,Order"]
        rows += [f"{name},,City,,,{fn},{date}," for name, fn, date in self.tournaments]
        (self.root / "tournaments.csv").write_text("\n".join(rows) + "\n")
        return check(
            results_dir=self.root / "results",
            tournaments_csv=self.root / "tournaments.csv",
            players_csv=self.root / "players.csv",
            milestone_dir=self.root / "no-milestone",
            build=False,
        )

    def assertProblem(self, fragment):
        problems = self.problems()
        self.assertTrue(
            any(fragment in p for p in problems),
            f"expected a problem mentioning {fragment!r}, got {problems}",
        )

    def test_a_good_corpus_passes(self):
        self.assertEqual(self.problems(), [])

    # -- the tournament list and the files ---------------------------------

    def test_misnamed_results_file(self):
        (self.root / "results/t-2026-results.csv").rename(
            self.root / "results/t-2026-results..csv")
        problems = self.problems()
        self.assertTrue(any("t-2026: no results file" in p for p in problems))
        self.assertTrue(any("t-2026-results..csv: not named" in p
                            and "did you mean 't-2026-results.csv'" in p
                            for p in problems), problems)

    def test_results_file_with_no_row(self):
        self.results("t2-2026", f"{HEADER}\nx,1,Ann Able,400,Bob Baker,350\n")
        self.assertProblem("no row in tournaments.csv has Filename t2-2026")

    def test_both_csv_and_tsv(self):
        self.results("t-2026", HEADER.replace(",", "\t") + "\n", ext="tsv")
        self.assertProblem("more than one results file")

    def test_bad_date(self):
        self.tournaments = [("Test Open", "t-2026", "11/01/2026")]
        self.assertProblem("Date '11/01/2026' is not yyyy-mm-dd")

    def test_duplicate_filename(self):
        self.tournaments.append(("Again", "t-2026", "2026-11-02"))
        self.assertProblem("Filename t-2026 is already used")

    def test_unquoted_comma_in_a_name(self):
        self.tournaments = [("Vancouver, BC", "t-2026", "2026-11-01")]
        self.assertProblem("9 columns, expected 8")

    def test_blank_filename_row_is_allowed(self):
        self.tournaments.append(("No results kept", "", "2020-02-15"))
        self.assertEqual(self.problems(), [])

    # -- inside a results file ---------------------------------------------

    def test_unknown_player(self):
        self.results("t-2026", f"{HEADER}\nx,1,Ann Abel,400,Bob Baker,350\n")
        self.assertProblem("'Ann Abel' is not in data/players.csv (did you mean 'Ann Able'?)")

    def test_trailing_space_in_a_name(self):
        self.results("t-2026", f"{HEADER}\nx,1,Ann Able ,400,Bob Baker,350\n")
        self.assertProblem("extra spaces")

    def test_bad_header(self):
        self.results("t-2026", "Round,Winner,Score\n1,Ann Able,400\n")
        self.assertProblem("header should start with")

    def test_score_not_a_number(self):
        self.results("t-2026", f"{HEADER}\nx,1,Ann Able,40O,Bob Baker,350\n")
        self.assertProblem("score '40O' is not a number")

    def test_sides_swapped(self):
        self.results("t-2026", f"{HEADER}\nx,1,Ann Able,300,Bob Baker,350\n")
        self.assertProblem("the winner scored less (300-350)")

    def test_a_tie_is_fine(self):
        self.results("t-2026", f"{HEADER}\nx,1,Ann Able,350,Bob Baker,350\n")
        self.assertEqual(self.problems(), [])

    def test_two_opponents_in_one_round(self):
        self.results("t-2026", f"""\
            {HEADER}
            x,1,Ann Able,400,Bob Baker,350
            x,1,Ann Able,400,Cy Cole,350
        """)
        self.assertProblem("Ann Able has 2 different opponents in round 1")

    def test_a_bye_in_a_round_already_played(self):
        self.results("t-2026", f"""\
            {HEADER}
            x,1,Ann Able,400,Bob Baker,350
            x,1,Ann Able,50,Bye,0
        """)
        self.assertProblem("Ann Able has 2 different opponents in round 1")

    def test_a_playoff_series_is_fine(self):
        self.results("t-2026", f"""\
            {HEADER}
            x,Final,Ann Able,400,Bob Baker,350
            x,Final,Bob Baker,400,Ann Able,350
            x,Final,Ann Able,400,Bob Baker,390
        """)
        self.assertEqual(self.problems(), [])

    def test_duplicate_row(self):
        self.results("t-2026", f"""\
            {HEADER}
            x,1,Ann Able,400,Bob Baker,350
            y,1,Ann Able,400,Bob Baker,350
        """)
        self.assertProblem("duplicate of line 2")

    def test_playing_themselves(self):
        self.results("t-2026", f"{HEADER}\nx,1,Ann Able,400,Ann Able,350\n")
        self.assertProblem("playing themselves")

    def test_blank_line(self):
        self.results("t-2026", f"{HEADER}\nx,1,Ann Able,400,Bob Baker,350\n\n")
        self.assertProblem("blank line")

    # -- number-keyed (Baxter) files ---------------------------------------

    def test_numbered_file_passes(self):
        self.results("t-2026", f"{NUMBERED}\nx,1,Ann Able,400,Bob Baker,350,0001,2\n")
        self.assertEqual(self.problems(), [])

    def test_unknown_number(self):
        self.results("t-2026", f"{NUMBERED}\nx,1,Ann Able,400,Bob Baker,350,1,99\n")
        self.assertProblem("player number 99 (Bob Baker) is not in data/players.csv")

    def test_number_for_someone_else(self):
        self.results("t-2026", f"{NUMBERED}\nx,1,Ann Able,400,Bob Baker,350,1,3\n")
        self.assertProblem("player number 3 is Cy Cole in data/players.csv")

    def test_missing_number(self):
        self.results("t-2026", f"{NUMBERED}\nx,1,Ann Able,400,Bob Baker,350,1,\n")
        self.assertProblem("Bob Baker has no player number")

    def test_half_a_number_pair(self):
        self.results("t-2026", f"{HEADER},Winner Number\nx,1,Ann Able,400,Bob Baker,350,1\n")
        self.assertProblem("missing 'opponent number'")

    def test_numbered_bye(self):
        self.results("t-2026", f"{NUMBERED}\nx,1,Ann Able,50,Bye,0,1,BYE\n")
        self.assertEqual(self.problems(), [])
