"""Statistics and data visualisation."""

from collections import Counter

from all_rating import process_old_results


class Statistics:
    """Statistics on playerdb."""

    def __init__(self, playerdb):
        self.db = playerdb

    def histogram(self, interval):
        bins = [interval * (p.rating // interval) for p in self.db.players.values()]
        return Counter(bins)


if __name__ == "__main__":
    print("Calculating ratings...")
    db, _ = process_old_results(display_progress=False)
    interval = 100
    print(f"Rating histogram (bin size = {interval}):")
    s = Statistics(db)
    h = s.histogram(interval)
    for k, v in sorted(h.items()):
        print(f"{k}\t{v}")
