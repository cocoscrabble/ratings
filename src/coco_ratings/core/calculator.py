"""The rating math: an implementation of the Norwegian rating system.

Pure computation over the :mod:`coco_ratings.core.types` data model — no file
I/O, no logging configuration, no imports outside the standard library. That is
deliberate and load-bearing: Baxter imports this to project live in-tournament
ratings, and must get the math without the file-format layer and without having
its own logging reconfigured. See ``plans/baxter-integration.md``.

Logging here is ordinary library logging: the messages are emitted, and it is
the *entry point's* job to decide whether anything listens (``cli.main`` and the
GUI attach the debug file handler; an importing application inherits its own
configuration).
"""

import logging
import math


class RatingsCalculator:
    """Class to organise ratings calculation code in one place."""

    def __init__(self, beta: float = 5):
        # tau is a tuning parameter to get as accurate results as
        # possible, and should be set up front. The value here is from
        # Taral Seierstad's rating system for Norwegian scrabble.
        self.tau = 90

        # beta is rating points per point of expected spread
        # eg, beta = 5, 100 ratings difference = 20 difference in
        # expected spread.
        # (Should we try varying beta based on ratings difference?)
        self.beta = beta

    def calc_initial_ratings(self, section):
        """Rate all unrated players in a section."""

        # Set pre-tournament rating to 1500 and deviation to 400 to start
        # Rerun the "calculate ratings for unrated players" part repeatedly,
        #   using the previously calculated rating as their initial rating
        #   until the output rating for these players equals the input rating

        # criteria for ratings convergence
        MAX_ITERATIONS = 50
        EPS = 0.0001

        # Manual seed
        MANUAL_SEED = 1500

        rated_opponent_sum = sum(p.init_rating for p in section.get_rated_players())
        rated_opponent_avg = rated_opponent_sum / len(section.get_players())
        if rated_opponent_avg < 300:
            logging.debug(
                "Rated player avg = %f; setting to manual seed", rated_opponent_avg
            )
            rated_opponent_avg = MANUAL_SEED

        converged = False
        iterations = 0
        while not converged and iterations < MAX_ITERATIONS:
            # converged is set to false in the loop below if any player's
            # rating changes in this iteration.
            converged = True

            for p in section.get_unrated_players():
                unrated_opps = [o for o in p.get_opponents() if o.is_unrated]
                if unrated_opps:
                    unrated_opps_pct = len(unrated_opps) / len(p.get_opponents())
                    if unrated_opps_pct >= 0.4:
                        p.set_init_rating(rated_opponent_avg)
                pre_rating = p.init_rating
                self.calc_new_rating_for_player(p)  # calculates rating as usual
                converged = converged and (abs(pre_rating - p.new_rating) < EPS)
                p.set_init_rating(p.new_rating)
                logging.debug(f"Rating unrated player {p}: {p.new_rating}")

            iterations = iterations + 1

    def _player_multiplier(self, player):
        # Calculate a multiplier based on initial ratings, then adjust it
        # based on career games.
        if player.init_rating > 2000:
            multiplier = 0.5
        elif player.init_rating > 1800:
            multiplier = 0.75
        else:
            multiplier = 1.0

        if player.career_games < 200:
            multiplier = 1.0
        elif player.career_games > 1000:
            multiplier = 0.5
        elif player.career_games > 100:
            multiplier = min(multiplier, 1.0 - (player.career_games / 1800))

        return multiplier

    def calc_new_rating_for_player(self, player):
        """An implementation of the Norwegian rating system.

        Rates a single player based on spread.
        """

        tau = self.tau
        beta = self.beta

        mu = player.init_rating
        logging.debug(
            "rating %s: initial = %d, multiplier = %f",
            player.name,
            mu,
            self._player_multiplier(player),
        )

        # Deviation is adjusted for inactive time when player is loaded
        sigma = player.init_rating_deviation

        rhos = []  # opponent uncertainty factor
        nus = []  # performance rating by game
        games = []  # games considered for rating
        for g in player.games:
            opponent = g.opponent
            if opponent == player or g.opp_score == 0 or g.score == 0:
                logging.debug("  skipping bye / forfeit")
                continue  # skip byes
            opponent_mu = opponent.init_rating
            opponent_sigma = opponent.init_rating_deviation
            g_rho = (beta**2) * (tau**2) + opponent_sigma**2
            g_nu = opponent_mu + (beta * g.spread)
            logging.debug(
                "  opp %s (μ=%.2f σ=%.2f) -> (ρ=%.2f ν=%.2f)",
                opponent.name,
                opponent_mu,
                opponent_sigma,
                g_rho,
                g_nu,
            )
            rhos.append(g_rho)
            nus.append(g_nu)
            games.append(g)
        # sum of inverse of uncertainty factors (to find 'effective'
        # deviation)
        sum1 = sum(1 / rho for rho in rhos)
        # sum of (INDIVIDUAL perfrat divided by opponent's sigma)
        sum2 = sum(nu / rho for nu, rho in zip(nus, rhos))
        # take invsquare of original dev, add inv of new sum of devs,
        # flip it back to get 'effective sigmaPrime'
        invsigma_prime = (1.0 / (sigma**2)) + sum1
        sigma_prime = 1.0 / invsigma_prime
        # calculate new rating using NEW sigmaPrime
        mu_prime = sigma_prime * ((mu / (sigma**2)) + sum2)
        delta = mu_prime - mu
        multiplier = self._player_multiplier(player)
        mu_prime = mu + (delta * multiplier)

        # Debug per-game rating change
        logging.debug("Per game rating changes for %s", player.name)
        base = sigma_prime * (mu / (sigma**2))
        n_games = len(games)
        base_delta = (player.init_rating - base) / n_games if n_games else 0
        logging.debug(
            "  base from opp ratings: %.2f (%d games, baseline Δ = %.2f)",
            base,
            n_games,
            base_delta,
        )
        sum_d = 0
        for game, g_rho, g_nu in zip(games, rhos, nus):
            g_mu = sigma_prime * (g_nu / g_rho)
            base += g_mu
            d = g_mu - base_delta
            sum_d += d
            logging.debug(
                "  %20s (%4d): \t Δ %6.2f \t Σ %6.2f \t d %6.2f \t Σd %6.2f \t ",
                game.opponent.name,
                game.spread,
                g_mu,
                base,
                d,
                sum_d,
            )

        # muPrime = mu + change
        # Don't set rating lower than 300
        logging.info("Rated %s: %f -> %f", player.name, player.init_rating, mu_prime)
        player.new_rating = max(round(mu_prime), 300)

        # if (player.new_rating < 1000): #believes all lousy players can improve :))
        #  sigmaPrime += math.sqrt(1000 - player.new_rating)
        try:
            player.new_rating_deviation = round(math.sqrt(sigma_prime), 2)
            logging.info(
                "New deviation for %s: %f -> %f",
                player.name,
                player.init_rating_deviation,
                player.new_rating_deviation,
            )
        except ValueError:
            print("ERROR: sigmaPrime {0}".format(sigma_prime))
