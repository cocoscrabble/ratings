"""Tests for the TOU file parser."""

import unittest

from .context import rating

TOUFILE = """\
*M25.05.2020 Glorious Towel Day Tournament
*A
Arthur Dent 2500 2 1300 +3 2450 4
Bertie Wooster 450 +1 250 4 2550 3
Sgt. Fred Colon 200 4 1300 1 400 2
Obelix 2400 3 2300 2 200 +1
*** END OF FILE ***

"""


class TestParser(unittest.TestCase):
    def test_basic(self):
        player_list = rating.PlayerList()
        toufile = TOUFILE.split("\n")
        t = rating.TouReader(player_list)
        t.parse_lines(toufile)
        self.assertEqual(len(t.sections), 1)
        s = t.sections[0]
        self.assertEqual(len(s.players), 4)
        players = ["Arthur Dent", "Bertie Wooster", "Sgt. Fred Colon", "Obelix"]
        self.assertEqual([x.name for x in s.players], players)
        p1 = s.players[0]
        g = p1.games[0]
        self.assertEqual(g.opponent.name, "Bertie Wooster")
        self.assertEqual(g.score, 500)
        self.assertEqual(g.opp_score, 450)
        self.assertEqual(p1.wins, 2.5)
        self.assertEqual(p1.losses, 0.5)


if __name__ == "__main__":
    unittest.main()
