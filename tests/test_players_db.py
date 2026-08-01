"""PlayerDB accepts either form of a player number.

`data/players.csv` stores numbers bare (`233`) because that is the identity key
the web players app uses, but the engine renders them zero-padded (`0233`) in
reports and legacy AUPAIR exports. Both forms get hand-edited into the file, so
reading normalizes rather than trusting the written form.
"""

import tempfile
import unittest
from pathlib import Path

from coco_ratings.players import PlayerDB
from coco_ratings.paths import PLAYERS_CSV


class PlayerNumberFormTest(unittest.TestCase):
    def test_either_form_reads_as_padded(self):
        db = PlayerDB([["alice", "233"], ["becky", "0233"], ["carol", " 7 "]])

        self.assertEqual(db.get_id("alice"), "0233")
        self.assertEqual(db.get_id("becky"), "0233")
        self.assertEqual(db.get_id("carol"), "0007")

    def test_non_numeric_id_is_left_alone(self):
        """A bad row must not crash the whole replay."""
        db = PlayerDB([["alice", "nonsense"]])
        self.assertEqual(db.get_id("alice"), "nonsense")

    def test_bye_is_zero(self):
        self.assertEqual(PlayerDB([]).get_id("Bye"), "0000")

    def test_reads_the_checked_in_file(self):
        db = PlayerDB.read_csv()
        self.assertGreater(len(db.name_to_id), 200)
        # Header skipped, and every id rendered as four digits.
        self.assertNotIn("Name", db.name_to_id)
        self.assertTrue(all(len(i) == 4 and i.isdigit() for i in db.name_to_id.values()))

    def test_padded_file_gives_the_same_ids(self):
        """Rewriting data/players.csv in padded form changes nothing."""
        bare = PlayerDB.read_csv()

        header, *rows = PLAYERS_CSV.read_text().splitlines()
        padded = [header]
        for row in rows:
            if not row:
                continue
            name, number = row.rsplit(",", 1)
            padded.append(f"{name},{int(number):04d}")
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "players.csv"
            f.write_text("\n".join(padded) + "\n")
            self.assertEqual(PlayerDB.read_csv(f).name_to_id, bare.name_to_id)


if __name__ == "__main__":
    unittest.main()
