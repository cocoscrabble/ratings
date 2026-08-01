"""Database of players: the single source of truth for player identity.

Maintained in `data/players.csv` (`Name,Number`), which is also what seeds the
web players app's identity table (`import_csv --current`). Numbers are stored
bare, the way the players app keys identity on them; the engine renders them
zero-padded to four digits, so `coco_id` is padded on the way in.
"""

import csv
from dataclasses import dataclass

from coco_ratings.paths import PLAYERS_CSV


# Exported as csv from google doc
DBFILE = PLAYERS_CSV


@dataclass
class PlayerEntry:
    name: str
    coco_id: str

    def __post_init__(self):
        self.name = self.name.strip()
        coco_id = self.coco_id.strip()
        # Stored bare (7), rendered padded (0007). Leave anything non-numeric
        # alone rather than crashing the whole replay over one bad row.
        self.coco_id = f"{int(coco_id):04d}" if coco_id.isdigit() else coco_id


class PlayerDB:
    @classmethod
    def read_csv(cls, file=DBFILE):
        rows = []
        with open(file, "r") as f:
            reader = csv.reader(f)
            next(reader)  # skip headings
            for row in reader:
                rows.append(row)
        return cls(rows)

    def __init__(self, data: list[list[str]]):
        entries = [PlayerEntry(*row) for row in data]
        self.name_to_id = {}
        self.id_to_name = {}
        for p in entries:
            self.name_to_id[p.name] = p.coco_id
            self.id_to_name[p.coco_id] = p.name

    def get_id(self, name):
        if name.lower() == "bye":
            return "0000"
        return self.name_to_id[name]


if __name__ == "__main__":
    pdb = PlayerDB.read_csv()
    for coco_id, name in sorted(pdb.id_to_name.items()):
        print(f"{coco_id} {name}")
