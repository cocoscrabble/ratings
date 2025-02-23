"""Tests for the ratings calculator."""

import unittest

from rating import GameResult, PlayerList, Section, RatingsCalculator


class TestRatings(unittest.TestCase):
    def setUp(self):
        # Set up a two-player, eight-game tournament.
        self.player_list = PlayerList()
        alice = self.player_list.find_or_add_player("alice")
        becky = self.player_list.find_or_add_player("becky")
        results = [
            (400, 300),
            (200, 450),
            (500, 450),
            (300, 300),
            (600, 300),
            (350, 500),
            (250, 400),
            (350, 300),
        ]
        for i, (a, b) in enumerate(results):
            alice.games.append(GameResult(i + 1, becky, a, b))
            becky.games.append(GameResult(i + 1, alice, b, a))
        section = Section("a")
        section.players = [alice, becky]
        for p in section.players:
            p.tally_results()
        self.section = section

    def test_unrated(self):
        alice, becky = self.section.players
        rc = RatingsCalculator()
        rc.calc_initial_ratings(self.section)
        # Alice should lose rating and Becky should gain it.
        self.assertLess(alice.init_rating, 1500)
        self.assertGreater(becky.init_rating, 1500)

    def test_one_rated(self):
        alice, becky = self.section.players
        alice.set_init_rating(1800)
        alice.is_unrated = False
        rc = RatingsCalculator()
        rc.calc_initial_ratings(self.section)
        # Alice's rating should not be touched. Becky should get a higher
        # rating than Alice.
        self.assertEqual(alice.init_rating, 1800)
        self.assertGreater(becky.init_rating, 1800)
        rc.calc_new_rating_for_player(alice)
        # Alice should not lose rating, since Becky was unrated
        self.assertEqual(alice.new_rating, 1800)

    def test_both_rated(self):
        alice, becky = self.section.players
        alice.set_init_rating(1800)
        alice.is_unrated = False
        becky.set_init_rating(1500)
        becky.is_unrated = False
        rc = RatingsCalculator()
        rc.calc_initial_ratings(self.section)
        # No ratings should change
        self.assertEqual(alice.init_rating, 1800)
        self.assertEqual(becky.init_rating, 1500)
        rc.calc_new_rating_for_player(alice)
        rc.calc_new_rating_for_player(becky)
        # Alice should now lose rating, and Becky gain it
        self.assertLess(alice.new_rating, 1800)
        self.assertGreater(becky.new_rating, 1500)


if __name__ == "__main__":
    unittest.main()
