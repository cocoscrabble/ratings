#!/usr/bin/python

from dataclasses import dataclass
from datetime import datetime, timedelta
import itertools
import logging
import math
import re
import sys


# Set up log file
logging.basicConfig(filename='coco_ratings.log', encoding='utf-8', level=logging.DEBUG)


MAX_DEVIATION = 150.0


class ParserError(Exception):
    def __init__(self, line, message):
        super().__init__(message)
        self.line = line
        self.message = message

    def __str__(self):
        return f'{self.message}\n{self.line}'

def show_exception(ex):
    _, _, exc_tb = sys.exc_info()
    template = (
            'An exception of type {0} occured at line {1}. '
            'Arguments:\n{2!r}')
    message = template.format(type(ex).__name__, exc_tb.tb_lineno, ex.args)
    print(message)


@dataclass
class ParsedResult:
    opponent_id: int
    score: int


@dataclass
class ParsedPlayerResults:
    player_name: str
    results: list[ParsedResult]


class ParsedSection:
    def __init__(self, name):
        self.name = name
        self.player_results = []

    def add_player_results(self, entry):
        self.player_results.append(entry)


class TouReader:
    """Read AUPAIR's .tou file format."""

    def __init__(self, player_list):
        self.player_list = player_list
        self.sections = []

    def parse(self, toufile):
        """Populates self.player_list with game results."""
        with open(toufile) as f:
            lines = f.readlines()
            try:
                self.parse_lines(lines)
            except ParserError as e:
                print(e)

    def parse_lines(self, lines):
        # Parse the file into our internal data structures.
        header, *results = lines
        self.parse_header(header)
        self.parsed_sections = self.parse_results(results)
        self.process_sections()

    def parse_header(self, header):
        # First line: *M31.12.1969 Tournament Name
        date, self.tournament_name = header.split(maxsplit=1)
        try:
            date = date[2:]  # strip off the '*M'
            self.tournament_date = datetime.strptime(date, '%d.%m.%Y')
        except ValueError:
            print(f'Cannot parse tournament date: {date} as dd.mm.yyyy')
            print("Using today's date")
            self.tournament_date = datetime.today()

    def parse_results(self, results):
        sections = []
        for line in results:
            if len(line) == 0 or line.startswith(' '):
                continue

            line = line.strip()
            if line == '*** END OF FILE ***':
                break
            elif line.startswith('*'):
                # We have begun a new section, designated by "*SectionName"
                sections.append(ParsedSection(line[1:]))
                continue
            elif len(line) < 3:
                # ignore ridiculously short lines
                continue

            player_results = self.parse_result_line(line)
            if not player_results:
                continue   # this is a high word listed at the top of the file
            sections[-1].add_player_results(player_results)
        return sections

    def process_sections(self):
        for s in self.parsed_sections:
            # Collect all the players in the section
            players = [
                    self.player_for_name(pr.player_name)
                    for pr in s.player_results
            ]

            # 1. Create a (players x rounds) matrix of GameResults,
            # filling in opponent and player_score, and leaving
            # opponent_score empty
            section_results = []
            for pr, player in zip(s.player_results, players):
                game_results = []
                for result in pr.results:
                    try:
                        opponent = players[result.opponent_id - 1]
                    except IndexError:
                        print(f'Invalid opponent id {result.opponent_id} for'
                                f' player {player.name} in section {s.name}')
                        sys.exit(1)
                    gr = GameResult(opponent, result.score, opp_score=None)
                    game_results.append(gr)
                section_results.append(game_results)

            # 2. Now iterate through the results again, and for each
            # round, look up the opponent's GameResult for that round. The
            # opponent's opponent_score will be the player's score.
            for pr in s.player_results:
                for i, result in enumerate(pr.results):
                    opp_gr = section_results[result.opponent_id - 1][i]
                    opp_gr.opp_score = result.score

            # 3. Now that we have fully filled in both sides of each
            # GameResult from the two half-results, we can add them to the
            # Player and then update the player's results fields.
            for sr, player in zip(section_results, players):
                player.games = sr
                player.tally_results()

            # 4. Now write out the fully parsed and populated Section
            section = Section(s.name)
            section.players = players
            self.sections.append(section)

    def player_for_name(self, name):
        player = self.player_list.find_or_add_player(name)
        if not player.is_unrated:
            player.adjust_initial_deviation(self.tournament_date)
        player.last_played = self.tournament_date
        return player

    def parse_result_line(self, line):
        """Parses result line into (name, [ParsedResult])."""
        # TOU FORMAT:
        # Mark Nyman           2488  16 2458  +4 2489 +25 2392   2  345  +8  348
        # Name       (score with prefix) (opponent number) (score with prefix) (opponent number)
        # Score Prefixes: 1 = Tie, 2 = Win
        # Opponent Prefixes: + = player went first
        def parse_int(s):
            try:
                return int(s)
            except ValueError:
                msg = f'Score field contained a non-digit: {s}'
                raise ParserError(line, msg)

        parts = line.split()
        # Read the first n parts with an alphabet in them as the name, and
        # everything else as the scores.
        name = list(itertools.takewhile(
            lambda x: re.search('[a-zA-Z]', x), parts))
        scores = parts[len(name):]
        name = ' '.join(name)
        if len(scores) < 2:
            # High score line; ignore it
            return None

        player_scores = []
        for i in range(0, len(scores), 2):
            score, opp = scores[i], scores[i + 1]
            score = parse_int(score) % 1000 # ignore the win/tie prefix
            opp = parse_int(opp) # ignore the + prefix too
            player_scores.append(ParsedResult(opp, score))
        return ParsedPlayerResults(name, player_scores)


class RatingsCalculator:
    """Class to organise ratings calculation code in one place."""

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
            logging.debug("Rated player avg = %f; setting to manual seed",
                rated_opponent_avg)
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
                logging.debug(f'Rating unrated player {p}: {p.new_rating}')

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

        # tau is a tuning parameter to get as accurate results as
        # possible, and should be set up front. The value here is from
        # Taral Seierstad's rating system for Norwegian scrabble.
        tau = 90

        # beta is rating points per point of expected spread
        # eg, beta = 5, 100 ratings difference = 20 difference in
        # expected spread.
        # (Should we try varying beta based on ratings difference?)
        beta = 5.0

        mu = player.init_rating
        logging.debug('rating %s: initial = %d', player.name, mu)

        # Deviation is adjusted for inactive time when player is loaded
        sigma = player.init_rating_deviation

        rhos = []  # opponent uncertainty factor
        nus = []  # performance rating by game
        for g in player.games:
            opponent = g.opponent
            if opponent == player:
                continue   # skip byes
            opponent_mu = opponent.init_rating
            opponent_sigma = opponent.init_rating_deviation
            rhos.append((beta ** 2) * (tau ** 2) + opponent_sigma ** 2)
            nus.append(opponent_mu + (beta * g.spread))
        # sum of inverse of uncertainty factors (to find 'effective'
        # deviation)
        sum1 = sum(1 / rho for rho in rhos)
        # sum of (INDIVIDUAL perfrat divided by opponent's sigma)
        sum2 = sum(nu / rho for nu, rho in zip(nus, rhos))
        # take invsquare of original dev, add inv of new sum of devs,
        # flip it back to get 'effective sigmaPrime'
        invsigma_prime = (1.0 / (sigma ** 2)) + sum1
        sigma_prime = 1.0 / invsigma_prime
        # calculate new rating using NEW sigmaPrime
        mu_prime = sigma_prime * ((mu / (sigma ** 2)) + sum2)
        delta = mu_prime - mu
        multiplier = self._player_multiplier(player)
        mu_prime = mu + (delta * multiplier)

        # muPrime = mu + change
        # Don't set rating lower than 300
        logging.debug(f'Rating {player.name}: {player.init_rating} -> {mu_prime}')
        player.new_rating = max(round(mu_prime), 300)

        # if (player.new_rating < 1000): #believes all lousy players can improve :))
        #  sigmaPrime += math.sqrt(1000 - player.new_rating)
        try:
            player.new_rating_deviation = round(math.sqrt(sigma_prime), 2)
        except ValueError:
            print('ERROR: sigmaPrime {0}'.format(sigma_prime))


class Tournament:
    """All data for a tournament."""

    def __init__(self, ratfile, toufile):
        self.player_list = PlayerList(ratfile)
        reader = TouReader(self.player_list)
        reader.parse(toufile)
        self.name = reader.tournament_name
        self.date = reader.tournament_date
        self.sections = reader.sections

    def calc_ratings(self):
        rc = RatingsCalculator()
        for s in self.sections:
            # FIRST: Calculate initial ratings for all unrated players
            rc.calc_initial_ratings(s)
            # THEN: Calculate new ratings for rated players
            for p in s.get_rated_players():
                rc.calc_new_rating_for_player(p)

    def output_results(self, output_file):  # now accepts 2 input (20161214)
        ResultsFile().write(output_file, self)

    def output_ratfile(self, out_file):
        byes = {
            'Yy bye', 'A Bye', 'B Bye', 'ZZ Bye', 'Zz Bye', 'Zy bye',
            'Bye One', 'Bye Two', 'Bye Three', 'Bye Four', 'Y Bye',
            'Z Bye',
            }
        players = [
            p for p in self.player_list.get_ranked_players()
            if p.name not in byes
        ]
        RatingsFile().write(out_file, players)

    def output_active_ratfile(self, out_file):
        with open('removed_people.txt', 'r') as d:
            deceased = [x.rstrip() for x in d.readlines()]
        players = []
        for p in self.player_list.get_ranked_players():
            threshold = self.date - timedelta(days=731)
            active = p.last_played > threshold
            if active and p.name not in deceased:
                players.append(p)

        RatingsFile().write(out_file, players)


class Section:
    """One section of a tournament."""

    def __init__(self, name):
        self.players = []   # List of Player objects
        self.highgame = {}   # should be dict containing Player, Round, Score
        self.name = name

    def get_players(self):
        return self.players

    def get_rated_players(self):
        return [p for p in self.players if not p.is_unrated]

    def get_unrated_players(self):
        return [p for p in self.players if p.is_unrated]

    def show(self):
        for p in self.players:
            print(f'Player: {p.name}')
            for i, g in enumerate(p.games):
                print(f'{i + 1:>2d}  {g}')



@dataclass
class GameResult:
    opponent: 'Player'
    score: int
    opp_score: int

    @property
    def spread(self):
        return self.score - self.opp_score

    def __str__(self):
        return f'{self.opponent.name:<24s} {self.score:3d} - {self.opp_score:3d}'


class Player:
    """Data for a single player."""

    def __init__(
            self,
            name,
            *,
            init_rating = 0,
            init_rating_deviation = 0.0,
            career_games = 0,
            is_unrated = False,
            last_played = None
    ):
        self.name = name
        self.career_games = career_games
        self.is_unrated = is_unrated
        self.set_init_rating(init_rating, init_rating_deviation)
        self.last_played = last_played or datetime(1999, 12, 31)

        # Always initialized to zero when creating the player
        self.wins = 0.0
        self.losses = 0.0
        self.spread = 0
        self.rating_change = 0
        self.new_rating = 0
        self.new_rating_deviation = 0.0
        self.games = [] # list of Game objects

    @classmethod
    def new_unrated(cls, name):
        return cls(
                name=name,
                init_rating=1500,
                init_rating_deviation=MAX_DEVIATION,
                last_played=datetime.today(),
                is_unrated=True
        )

    def __str__(self):
        return self.name

    def tally_results(self):
        self.update_career_games()
        for g in self.games:
            self.add_game_result(g.spread)

    def set_init_rating(self, rating, dev=MAX_DEVIATION):
        self.init_rating = rating
        self.init_rating_deviation = dev

        if self.init_rating_deviation == 0:
            self.init_rating_deviation = MAX_DEVIATION
        else:
            self.init_rating_deviation = dev

        self.new_rating = rating
        self.new_rating_deviation = dev

    def add_game_result(self, spr):
        self.spread += spr
        if spr == 0:
            self.wins += 0.5
            self.losses += 0.5
        elif spr > 0:
            self.wins += 1
        else:
            self.losses += 1

    def update_career_games(self):
        for game in self.games:
            if game.opponent != self and game.opponent != 'Zz Bye':
                self.career_games += 1

    def get_score_by_round(self, r):
        return self.games[r].score

    def get_opponent_by_round(self, r):
        return self.games[r].opponent

    def get_opponents(self):
        """Returns a list of all opponents."""
        return [g.opponent for g in self.games]

    def adjust_initial_deviation(self, tournament_date):
        try:
            c = 10
            inactive_days = int((tournament_date - self.last_played).days)
            self.init_rating_deviation = min(
                math.sqrt(
                    math.pow(self.init_rating_deviation, 2)
                    + (math.pow(c, 2) * inactive_days)
                ),
                MAX_DEVIATION,
            )
        except Exception as ex:
            print(
                'DEBUG {0} {1} {2} {3}'.format(
                    self.name,
                    self.last_played,
                    inactive_days,
                    self.init_rating_deviation,
                )
            )
            show_exception(ex)


class RatingsFile:
    """Player rating data file."""

    def __init__(self):
        self.col_fmt = '{:9}{:20}{:5}{:5} {:9}{:6}\n'

    def parse(self, ratfile):
        players = {}
        with open(ratfile) as f:
            next(f)   # skip headings
            for row in f:
                p = self._read_player(row)
                players[p.name] = p
        return players

    def _header(self):
        return self.col_fmt.format(
                'NICK', 'Name', 'Games', ' Rat', 'last_played', 'New Dev')

    def write(self, ratfile, players):
        with open(ratfile, 'w') as f:
            f.write(self._header())
            for p in players:
                out = self.col_fmt.format(
                        '',
                        p.name,
                        p.career_games,
                        p.new_rating,
                        p.last_played.strftime('%Y%m%d'),
                        p.new_rating_deviation,
                        )
                f.write(out)

    def _read_player(self, row):
        # nick = row[0:4]
        # state = row[5:8]
        name = row[9:29].strip()
        career_games = int(row[30:34])
        rating = int(row[35:39])
        last_played = self._read_date(row)
        try:
            rating_deviation = float(row[49:])
        except (ValueError, IndexError):
            rating_deviation = MAX_DEVIATION
        return Player(
                name=name,
                init_rating=rating,
                init_rating_deviation=rating_deviation,
                career_games=career_games,
                last_played=last_played,
                is_unrated=False
        )

    def _read_date(self, row):
        # DEVELOPING TOLERANCE FOR HORRIBLY FORMATTED TOU FILES GRRR!
        # Try reading the date in three different places (40, 39, 41)
        # and two different formats (yyyymmdd and yyyyddmm)
        for col in (40, 39, 41):
            for fmt in ('%Y%m%d', '%Y%d%m'):
                try:
                    # Return as soon as we parse a date.
                    return datetime.strptime(row[col : col + 8], fmt)
                except ValueError:
                    logging.debug(f'Failed parse: {fmt} @ {col}\n  {row}\n')

        # If we reach here we have not found a date anywhere we've looked.
        logging.debug(f'Could not parse last played date\n  {row}\n')
        return datetime.strptime('20060101', '%Y%m%d')


class ResultsFile:

    def __init__(self):
        self.col_fmt = '{:21} {:10} {:7} {:8} {:8} {:8}'


    def write(self, output_file, tournament):
        with open(output_file, 'w') as f:
            f.write(f'{tournament.name}\n{tournament.date.date()}\n')
            for s in tournament.sections:
                self._write_section(f, s)

    def _get_sorted_players(self, section):
        return sorted(section.get_players(),
                key=lambda x: (x.wins * 100000) + x.spread,
                reverse=True)

    def _header(self):
        return self.col_fmt.format(
                'NAME', 'RECORD', 'SPREAD', 'OLD RAT', 'NEW RAT', 'NEW DEV')

    def _write_section(self, out, section):
        out.write('Section {:1}\n'.format(section.name))
        out.write(self._header())
        out.write('\n')

        for p in self._get_sorted_players(section):
            out.write(
                    self.col_fmt.format(
                    p.name,
                    f'{p.wins}-{p.losses}',
                    p.spread,
                    p.init_rating,
                    p.new_rating,
                    p.new_rating_deviation
                )
            )
            out.write('\n')
        out.write('\n')   # section break

        for p in section.get_unrated_players():
            out.write('{:21} is unrated \n'.format(p.name))
        out.write('\n')   # section break


class PlayerList:
    """A global ratings list."""

    def __init__(self, ratfile=None):
        if ratfile:
            # Load all current players from ratfile
            self.players = RatingsFile().parse(ratfile)
        else:
            self.players = {}

    def add_new_player(self, name):
        self.players[name] = Player.new_unrated(name)

    def get_ranked_players(self):
        return sorted(
            self.players.values(),
            key=lambda p: p.new_rating,
            reverse=True,
        )

    def find_or_add_player(self, name):
        if name not in self.players:
            self.add_new_player(name)
        return self.players[name]


if __name__ == '__main__':
    t = Tournament(None, 'testdata/isropn20.tou')
    t.calc_ratings()
    t.output_results('test.RT')
    t.output_ratfile('test.dat')
