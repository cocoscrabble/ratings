"""Database of players.

Currently maintained in a CSV file.
"""

import csv
from dataclasses import dataclass


# Exported as csv from google doc
DBFILE = "data/players.csv"


@dataclass
class Player:
    name: str
    coco_id: str

    def __post_init__(self):
        self.name = self.name.strip()
        self.coco_id = self.coco_id.strip()


class PlayerDB:
    @classmethod
    def read_csv(cls, file=DBFILE):
        rows = []
        with open(file, "r") as f:
            reader = csv.reader(f)
            for row in reader:
                rows.append(row)
        return cls(rows)

    def __init__(self, data: list[list[str]]):
        entries = [Player(*row) for row in data]
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
