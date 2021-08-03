#!/usr/bin/python

from dataclasses import dataclass, field
import datetime
import itertools
import math
import os
import re
import string
import sys
import time

global tournamentDate
tournamentDate = 20200101
global MAX_DEVIATION
MAX_DEVIATION = 150.0


class ParserError(Exception):
    def __init__(self, lineno, line, message):
        self.line = line
        self.message = message


@dataclass
class Result:
    opponent_id: int
    score: int


class TouReader:
    """Read AUPAIR's .tou file format."""

    def __init__(self, toufile, player_list):
        self.filename = toufile
        self.player_list = player_list
        self.sections = []
        self.parse(toufile)

    def parse(self, toufile):
        with open(toufile) as f:
            lines = f.readlines()

        # Parse the file into our internal data structures.
        header, *results = lines
        self.parse_header(header)
        self.parse_results(results)

        # Calculate each player's wins and spread.
        for s in self.sections:
            s.tallyPlayerResults()

    def parse_header(self, header):
        # First line: *M31.12.1969 Tournament Name
        date, self.tournament_name = header.split(' ', 1)
        try:
            self.tournament_date = datetime.datetime.strptime(date[2:], '%m.%d.%Y')
        except ValueError:
            print(f'Cannot parse tournament date: {date} as dd.mm.yyyy')
            print("Using today's date")
            self.tournament_date = datetime.date.today()

    def parse_results(self, results):
        for line in results:
            if len(line) == 0 || line.startswith(' '):
                continue

            line = line.strip()
            if line == '*** END OF FILE ***':
                break
            elif line.startswith('*'):
                # We have begun a new section, designated by "*SectionName"
                current_section = Section(line[1:])
                self.sections.append(current_section)
                continue
            elif len(line) < 3:
                # ignore ridiculously short lines
                continue

            player_name, scores = self.parse_result_line(line)
            if not player_name:
                continue   # this is a high word listed at the top of the file

            current_player = self.player_list.find_or_add_player(player_name)
            current_section.addPlayer(current_player)
            if not current_player.isUnrated:
                current_player.adjustInitialDeviation(self.tournament_date)
            current_player.setLastPlayed(self.tournament_date)
            self.add_scores_to_section(current_section, scores)

    def parse_result_line(self, line):
        """Parses result line into (name, [Result])."""
        # TOU FORMAT:
        # Mark Nyman           2488  16 2458  +4 2489 +25 2392   2  345  +8  348
        # Name       (score with prefix) (opponent number) (score with prefix) (opponent number)
        # Score Prefixes: 1 = Tie, 2 = Win
        # Opponent Prefixes: + = player went first
        def parse_int(s):
            try:
                return int(s)
            except ValueError:
                msg = 'Score field contained a non-digit: {score}'
                raise ParserError(line, msg)

        parts = line.split(' ')
        # Read the first n parts with an alphabet in them as the name, and
        # everything else as the scores.
        name = list(itertools.takewhile(
            lambda x: re.search('[a-zA-Z]', x), parts))
        scores = parts[len(name):]
        name = ' '.join(name)
        if len(scores) < 2:
            # High score line; ignore it
            return None, None

        player_scores = []
        for i in range(0, len(scores), 2):
            score, opp = parts[i], parts[i + 1]
            score = parse_int(score) % 1000 # ignore the win/tie prefix
            opp = parse_int(opp) # ignore the + prefix too
            player_scores.append(Result(opp, score))
        return name, player_scores

    def add_scores_to_section(self, current_section, scores):
        for round_number, result in enumerate(scores):
            # 1. get the nth round. if it doesn't exist, create it.
            rnd = current_section.getRoundByNumber(round_number)
            if rnd is None:
                rnd = Round()
                current_section.addRound(rnd)

            # 2. Find the opponent
            try:
                opponent = current_section.getPlayerByNumber(result.opponent_id)
            except IndexError:
                msg = f'Fewer opponents than rounds. Current player: {player_name}'
                raise ParserError(line, msg)

            # 3. If we know the opponent, we have already parsed their line
            # and created the game object. If not, create a new game
            # object. We will match the opponent to the current player
            # when we parse them
            game = rnd.getGameByPlayer(opponent)
            if game is None:
                game = Game()
                rnd.addGame(game)
            game.addPlayerResult(current_player, result.score)


class Tournament(object):
    def __init__(self, ratfile, toufile):
        try:
            self.globalList = PlayerList(ratfile)
            reader = TouReader(toufile, globalList)
            self.sections = reader.sections
        except Exception as ex:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            template = 'An exception of type {0} occured at line {1}. Arguments:\n{2!r}'
            message = template.format(type(ex).__name__, exc_tb.tb_lineno, ex.args)
            print(message)

    def calcRatings(self):
        ##### FIRST here -- calculate ratings for unrated players first
        #####   Set their pre-tournament rating to 1500 and deviation to 400 to start
        #####   Rerun the "calculate ratings for unrated players" part repeatedly,
        #####     using the previously calculated rating as their initial rating
        #####     until the output rating for these players equals the input rating
        #####   THEN for rated players only:
        MAX_ITERATIONS = 50
        for s in self.sections:
            converged = False
            iterations = 0
            opponentSum = 0.0
            manualSeed = 1500.0

            # prepares the average rating of the field
            for p in s.getUnratedPlayers():
                opponentMu = p.initRating
                opponentSum += opponentMu

            opponentAverage = opponentSum / float(len(s.getPlayers()))

            while not converged and iterations < MAX_ITERATIONS:
                converged = True   # i.e. when in the loop and 'False' is returned, keep iterating

                for p in s.getUnratedPlayers():
                    unratedOppsPct = 0.0
                    unratedOpps = 0.0
                    try:
                        unratedOpps = float(len([opp for opp in p.getOpponents() if opp.isUnrated]))
                        totalOpps = float(len(p.getOpponents()))
                        unratedOppsPct = float(unratedOpps / totalOpps)
                    except ZeroDivisionError:
                        unratedOppsPct = 0.0
                    if unratedOppsPct >= 0.4:
                        try:
                            p.setInitRating(opponentAverage)
                            preRating = p.initRating
                        except ValueError:
                            p.setInitRating(manualSeed)
                            print(f'Using manual seed of {manualSeed}')
                            preRating = p.initRating
                    else:
                        preRating = p.initRating
                    p.calcNewRatingBySpread()   # calculates rating as usual
                    converged = converged and preRating == p.newRating
                    p.setInitRating(p.newRating)
                    p.setInitDeviation(MAX_DEVIATION)
                    print(f'Rating unrated player {p}: {p.newRating}\n')

                iterations = iterations + 1

            for p in s.getRatedPlayers():
                p.calcNewRatingBySpread()

    def outputResults(self, outputFile):  # now accepts 2 input (20161214)
        # handle should be open for writing
        for s in self.sections:
            outputFile.write('Section {:1}'.format(s.name))
            outputFile.write(
                '{:21} {:10} {:7} {:8} {:8}'.format(
                    'NAME', 'RECORD', 'SPREAD', 'OLD RAT', 'NEW RAT'
                )
            )
            outputFile.write('\n')
            for p in sorted(
                s.getPlayers(),
                key=lambda x: (x.wins * 100000) + x.spread,
                reverse=True,
            ):
                outputFile.write(
                    '{:21} {:10} {:7} {:8} {:8}'.format(
                        p.name,
                        f'{p.wins}-{p.losses}',
                        p.spread,
                        p.initRating,
                        p.newRating,
                    )
                )
                outputFile.write('\n')

        outputFile.write('\n')   # section break

        for p in s.getUnratedPlayers():
            outputFile.write('{:21} is unrated \n'.format(p.name))
        outputFile.write('\n')   # section break

        rootDir = '../'
        touname = self.tournamentName
        for root, dirs, files in os.walk(rootDir):
            for filename in [
                y for y in files if 'tou' in y
            ]:   # for ANY file ending with .tou
                TOUFILE = os.path.join(root, filename)

    def outputRatfile(self, outFile):
        outFile.write(
            'NICK     {:20}{:5}{:5} {:9}{:6}\n'.format(
                'Name', 'Games', ' Rat', 'Lastplayed', 'New Dev'
            )
        )
        for p in self.globalList.get_ranked_players():
            if p.name in [
                'Yy bye',
                'A Bye',
                'B Bye',
                'ZZ Bye',
                'Zz Bye',
                'Zy bye',
                'Bye One',
                'Bye Two',
                'Bye Three',
                'Bye Four',
                'Y Bye',
                'Z Bye',
            ]:
                continue
            try:
                outFile.write(
                    '         {:20}{:5}{:5} {:9}{:6} \n'.format(
                        p.name,
                        p.careerGames,
                        p.newRating,
                        p.lastPlayed.strftime('%Y%m%d'),
                        p.newRatingDeviation,
                    )
                )
            except ValueError:
                print(
                    str(p.name)
                    + "'s lastPlayed was"
                    + str(p.lastPlayed)
                )

    # inserted p.getNewLastPlayed on 15th Dec
    # print("This tournament's rating is complete :)")

    def outputActiveRatfile(self, outFile):
        outFile.write(
            'NICK     {:20}{:5}{:5} {:9}{:6}\n'.format(
                'Name', 'Games', ' Rat', 'Lastplayed', 'New Dev'
            )
        )
        with open('removed_people.txt', 'r') as d:
            deceased = [x.rstrip() for x in d.readlines()]
        try:
            for p in self.globalList.get_ranked_players():
                active = (
                    p.lastPlayed
                    > self.tournamentDate - datetime.timedelta(days=731)
                )
                if p.name in deceased or not active:
                    pass
                else:
                    outFile.write(
                        '         {:20}{:5}{:5} {:9}{:6} \n'.format(
                            p.name,
                            p.careerGames,
                            p.newRating,
                            p.lastPlayed.strftime('%Y%m%d'),
                            p.newRatingDeviation,
                        )
                    )
        except Exception as ex:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            template = 'An exception of type {0} occured at line {1}. Arguments:\n{2!r}'
            message = template.format(
                type(ex).__name__, exc_tb.tb_lineno, ex.args
            )
            print(message)


class Section(object):
    def __init__(self, name):
        self.players = []   # List of Player objects
        self.rounds = []   # list of Round objects
        self.highgame = {}   # should be dict containing Player, Round, Score
        self.name = name

    def addPlayer(self, player):
        self.players.append(player)

    def addRound(self, rnd):
        self.rounds.append(rnd)

    def getPlayers(self):
        return self.players

    def getRatedPlayers(self):
        return [p for p in self.players if not p.isUnrated]

    def getUnratedPlayers(self):
        return [p for p in self.players if p.isUnrated]

    def getRoundByNumber(self, number):
        try:
            return self.rounds[number]
        except IndexError:
            return None

    def getPlayerByNumber(self, number):
        try:
            # player numbers in the tou file are 1-based
            return self.players[number - 1]
        except IndexError:
            return None

    def tallyPlayerResults(self):
        for p in self.players:
            p.tallyResults()


class Player(object):

    def __init__(
            self,
            name,
            *,
            initRating = 0,
            initRatingDeviation = 0.0,
            careerGames=0,
            isUnrated=False,
            lastPlayed=None
    ):
        self.name = name
        self.careerGames = careerGames
        self.isUnrated = isUnrated
        self.setInitRating(initRating, initRatingDeviation)
        self.lastPlayed = lastPlayed or datetime.date(1999, 12, 31)

        # Always initialized to zero when creating the player
        self.wins = 0.0
        self.losses = 0.0
        self.spread = 0
        self.ratingChange = 0
        self.newRating = 0
        self.newRatingDeviation = 0.0
        self.games = [] # list of Game objects

    @classmethod
    def new_unrated(cls, name):
        return cls(
                name=name,
                initRating=1500,
                initRatingDeviation=MAX_DEVIATION,
                lastPlayed=datetime.datetime.today(),
                isUnrated=True
        )

    def __str__(self):
        return self.name

    def tallyResults(self):
        self.updateCareerGames()
        for g in self.games:
            score1 = g.getMyScore(self)
            score2 = g.getOpponentScore(self)
            if score1 > score2:
                self.addGameResult(True, score1 - score2)
            else:
                # for Ties, the "win" boolean doesn't matter
                self.addGameResult(False, score2 - score1)

    def setInitRating(self, rating, dev=MAX_DEVIATION):
        self.initRating = rating
        self.initRatingDeviation = dev

        if self.initRatingDeviation == 0:
            self.initRatingDeviation = MAX_DEVIATION
        else:
            self.initRatingDeviation = dev

        self.newRating = rating
        self.newRatingDeviation = dev

    def setInitDeviation(self, deviation):
        self.initRatingDeviation = deviation

    def setLastPlayed(self, date):
        self.lastPlayed = date

    def getName(self):
        return self.name

    def getDate(self):
        return self.tournamentDate

    def getNewRating(self):
        return self.newRating

    def getNewRatingDeviation(self):
        return self.newRatingDeviation

    def getCareerGames(self):
        return self.careerGames

    def setUnrated(self, unrated):
        self.isUnrated = unrated

    def addGameResult(self, win, spr):
        if spr == 0:
            self.wins += 0.5
            self.losses += 0.5
        elif win:
            self.wins += 1
            self.spread += spr
        else:
            self.losses += 1
            self.spread -= spr

    def addGame(self, game):
        self.games.append(game)

    def updateCareerGames(self):
        for game in self.games:
            if self.getOpponentByGame(game) != self:
                self.careerGames += 1
            if self.getOpponentByGame(game) == 'Zz Bye':
                self.careerGames -= 1

    def getScoreByRound(self, r):
        return self.games[r].getResult().self

    def getOpponentByRound(self, r):
        return [p for p in self.games[r].getResult().keys() if (p != self)][0]

    def getOpponentByGame(self, g):
        # return self for byes
        try:
            return [p for p in g.getResult().keys() if (p != self)][0]
        except IndexError:
            return self

    def getOpponents(self):
        return [
            self.getOpponentByGame(g) for g in self.games
        ]   # returns a list of all opponents

    def adjustInitialDeviation(self, tournamentDate):
        try:
            c = 10
            inactiveDays = int((tournamentDate - self.lastPlayed).days)
            self.initRatingDeviation = min(
                math.sqrt(
                    math.pow(self.initRatingDeviation, 2)
                    + (math.pow(c, 2) * inactiveDays)
                ),
                MAX_DEVIATION,
            )
        except Exception as ex:
            print(
                'DEBUG {0} {1} {2} {3}'.format(
                    self.name,
                    self.lastPlayed,
                    inactiveDays,
                    self.initRatingDeviation,
                )
            )
            exc_type, exc_obj, exc_tb = sys.exc_info()
            template = 'An exception of type {0} occured at line {1}. Arguments:\n{2!r}'
            message = template.format(
                type(ex).__name__, exc_tb.tb_lineno, ex.args
            )
            print(message)

    def calcNewRatingBySpread(self):   # this rates 1 player
        """
        An implementation of the Norwegian rating system.
        """
        try:
            mu = self.initRating
            #      print(self.name)
            #      print(self.initRating)

            #      tau = 70.0 + (float(self.careerGames)/100.0)
            tau = 90
            #      if mu > 2000:
            #        tau = 100
            #      elif mu > 1800:
            #        tau = 95
            #      else:
            #        tau = 90

            # Deviation is adjusted for inactive time when player is loaded
            sigma = float(self.initRatingDeviation)

            rho = []  # opponent uncertainty factor
            nu = []  # performance rating by game
            for g in self.games:
                opponent = self.getOpponentByGame(g)
                if opponent == self:
                    continue   # skip byes
                opponentMu = opponent.initRating
                # Try varying beta based on ratings difference.
                # beta is rating points per point of expected spread
                # eg, beta = 5, 100 ratings difference = 20 difference in
                # expected spread
                beta = 5

                opponentSigma = opponent.initRatingDeviation
                rho.append(
                    float(((beta ** 2) * (tau ** 2)) + opponentSigma ** 2)
                )
                gameSpread = g.getResult()[self] - g.getResult()[opponent]
                nu.append(float(opponentMu + (beta * gameSpread)))
            sum1 = 0.0
            sum2 = 0.0
            for m in range(len(rho)):   # for each item in the rho list
                # summation of inverse of uncertainty factors (to find
                # 'effective' deviation)
                sum1 += (1.0 / rho[m])
                # summation of (INDIVIDUAL perfrat divided by opponent's sigma)
                sum2 += (nu[m] / rho[m])
            # take invsquare of original dev, add inv of new sum of devs,
            # flip it back to get 'effective sigmaPrime'
            invsigmaPrime = (1.0 / (sigma ** 2)) + sum1
            sigmaPrime = (1.0 / invsigmaPrime)
            # calculate new rating using NEW sigmaPrime
            muPrime = sigmaPrime * ((mu / (sigma ** 2)) + sum2)

            delta = muPrime - mu
            if self.careerGames < 200:
                multiplier = 1.0
            elif mu > 2000:
                multiplier = 0.5
            elif mu > 1800:
                multiplier = 0.75
            else:
                multiplier = 1.0

            if self.careerGames > 1000:
                multiplier = 0.5
            elif self.careerGames > 100:
                multiplier = min(
                    multiplier, 1.0 - (float(self.careerGames) / 1800)
                )

            muPrime = mu + (delta * multiplier)

        except Exception as ex:
            print('Error calculating ratings for {0}'.format(self.name))
            print(
                'beta {0} tau {1} mu {2} sigma {3}'.format(
                    beta, tau, mu, sigma
                )
            )
            exc_type, exc_obj, exc_tb = sys.exc_info()
            template = 'An exception of type {0} occured at line {1}. Arguments:\n{2!r}'
            message = template.format(
                type(ex).__name__, exc_tb.tb_lineno, ex.args
            )
            print(message)

        # muPrime = mu + change
        self.newRating = int(round(muPrime))

        if self.newRating < 300:
            self.newRating = 300

        # if (self.newRating < 1000): #believes all lousy players can improve :))
        #  sigmaPrime += math.sqrt(1000 - self.newRating)
        try:
            self.newRatingDeviation = round(math.sqrt(sigmaPrime), 2)
        except ValueError:
            print('ERROR: sigmaPrime {0}'.format(sigmaPrime))


class Round(object):
    def __init__(self):
        self.games = []

    def getGameByPlayer(self, player):
    """Returns a game object if a game w/ that player exists in the round, else
    returns None
    """
        for game in self.games:
            if player in game.getPlayers():
                return game
        return None

    def addGame(self, game):
        self.games.append(game)

    def getGames(self):
        return self.games


class Game(object):
    def __init__(self):
        # s1 and s2 are integers
        # r is a boolean -- is this a rated game?
        self.result = {}   # dict with { PlayerObject: score }
        self.rated = True

    def addPlayerResult(self, player, score):
        self.result[player] = score
        player.addGame(self)

    def getPlayers(self):
        return self.result.keys()

    def isRated(self):
        return self.rated

    def setRated(self, r):
        self.rated = r

    def getResult(self):
        return self.result

    def getMyScore(self, player):
        return self.result[player]

    def getOpponentScore(self, player):
        try:
            opponent = [p for p in self.result.keys() if (p != player)][0]
            return self.result[opponent]
        except IndexError:
            # If it is a bye and the player was paired with themself, return
            # their score here
            return self.result[player]


class PlayerList(object):
    """A global ratings list."""

    def __init__(self, ratfile):
        # Load all current players from ratfile

        self.players = {}

        with open(ratfile) as f:
            next(f)   # skip headings
            for row in f:
                p = self.read_player(row)
                self.players[p.name] = p

    def read_player(self, row):
        nick = row[0:4]
        state = row[5:8]
        name = row[9:29].strip()
        careerGames = int(row[30:34])
        rating = int(row[35:39])
        lastPlayed = self.read_date(row)
        try:
            ratingDeviation = float(row[49:])
        except (ValueError, IndexError):
            ratingDeviation = MAX_DEVIATION
        return Player(
                name=name,
                initRating=rating,
                initRatingDeviation=ratingDeviation
                careerGames=careerGames,
                lastPlayed=lastPlayed,
                unrated=False
        )

    def read_date(self, row):
        # DEVELOPING TOLERANCE FOR HORRIBLY FORMATTED TOU FILES GRRR!
        last_played = None
        with open('log.txt', 'a+') as logfile:
            # Try reading the date in three different places (40, 39, 41)
            # and two different formats (yyyymmdd and yyyyddmm)
            for col in (40, 39, 41):
              for fmt in ('%Y%m%d', '%Y%d%m'):
                  try:
                      last_played = datetime.strptime(row[col : col + 8])
                  except ValueError:
                      logfile.write(f'Failed parse: {nick} {fmt} @ {col}')
            if last_played is None:
                logfile.write('Could not parse last played date\n')
                logfile.write(row + '\n')
                last_played = datetime.strptime('20060101', '%Y%m%d')
        return last_played

    def add_new_player(self, name):
        self.players[name] = Player.new_unrated(name)

    def get_ranked_players(self):
        for p in sorted(
            self.players.values(),
            key=lambda p: p.newRating,
            reverse=True,
        )

    def find_or_add_player(self, name):
        if name not in self.players:
            self.add_new_player(name)
        return self.players[name]
