from datetime import datetime
import glob
import os
from io import StringIO

from rating import Tournament, TabularResultWriter, RTFileWriter

ALL = [
    ("loco-2021", "2021-03-01"),
    ("pabst-2021", "2021-04-01"),
    ("charlottesville-2021", "2021-05-01"),
    ("seattle-2021", "2021-06-01"),
    ("hoodriver-2022", "2022-01-01"),
    ("sandiego-2022", "2022-02-01"),
]

def show_file(f):
    f.seek(0)
    for line in f.readlines():
        print(line.strip())


def main():
    d = os.path.join(os.path.dirname(__file__), "results")
    results = glob.glob(f"{d}/*results.?sv")
    ratings = glob.glob(f"{d}/*ratings.?sv")
    hres = {os.path.basename(f)[:-12]: f for f in results}
    hrat = {os.path.basename(f)[:-12]: f for f in ratings}
    for prefix, date in ALL:
        print(f"Reading {prefix}")
        date = datetime.strptime(date, '%Y-%m-%d')
        res = hres[prefix]
        rat = hrat[prefix]
        t = Tournament(rat, res, prefix, date)
        t.calc_ratings()
        res_out = StringIO('')
        rat_out = StringIO('')
        TabularResultWriter().write(res_out, t)
        RTFileWriter().write(rat_out, t.player_list.get_ranked_players())
        show_file(res_out)
        print("-------------------------")
        show_file(rat_out)
        print("-------------------------")
        
        
        


    


if __name__ == '__main__':
    main()

