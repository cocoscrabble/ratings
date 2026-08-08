# Code changes that moved a rating

200 commits touched .py. 80 changed someone's rating, 54 changed nothing, 66 could not be replayed. Mode: each tree as committed.

## Engine changes that moved ratings

Commits whose Python diff is not purely the chronological tournament list. This is the answer to the question — 4 of them.

| date | commit | subject | players moved | biggest move | kind | data |
|---|---|---|---|---|---|---|
| 2022-07-07 | `da077423a3` | skip rating games against the bye player | 12 | Joe Roberdeau 1391→1372 | code | no |
| 2022-07-08 | `906445ab82` | skip forfeit losses for rating purposes | 1 | Winter 1780→1798 | code | no |
| 2024-03-10 | `546051b407` | Apply rating deviation adjustment in the PlayerDB adjust_tournament method | 150 | Jesse Day 1996→1838 | code | no |
| 2025-11-16 | `c5aa5ff05a` | Read the chronological list of tournaments from a csv file | 78 | Michael McKenna 1635→1641 | mixed | yes |

## Tournament-list edits

Until the list moved to data/tournaments.csv (`c5aa5ff05a`, 2025-11-16) it lived in all_rating.py, so adding a tournament was a .py change. These 76 commits move ratings because they add results, not because the maths changed.

| date | commit | subject | players moved | biggest move | kind | data |
|---|---|---|---|---|---|---|
| 2022-05-10 | `55bdc46269` | add some tournament results | 36 | Jesse Day 2084→2039 | tournament-list | yes |
| 2022-05-24 | `3ec77331fd` | add 3m tourney results | 10 | Chris Lipe 1930→1887 | tournament-list | yes |
| 2022-06-16 | `0c1d2dcb60` | add madison results | 10 | Melissa Routzahn 1452→1552 | tournament-list | yes |
| 2022-06-26 | `bc51ab0676` | add stl 2022 ratings | 12 | Rob Robinsky 2035→1978 | tournament-list | yes |
| 2022-07-08 | `c8678f48cf` | add wgpo earlybird | 14 | Ayotunde Adeyeri 1517→1564 | tournament-list | yes |
| 2022-07-13 | `b43afa1749` | add wordcup main event results | 71 | Charles Reinke 2041→1887 | tournament-list | yes |
| 2022-08-21 | `8c20759bda` | add some tournament results | 20 | Marty Gold 1723→1600 | tournament-list | yes |
| 2022-10-08 | `1c594f24eb` | add loco-22 and brattleboro-22 results | 27 | Jesse Matthews 1646→1754 | tournament-list | yes |
| 2022-10-09 | `8840bb66f9` | add pabst 2022 results | 14 | Gary Smart 1363→1441 | tournament-list | yes |
| 2022-11-14 | `aca0f60e66` | add slingerlands 2022 results | 18 | Ben Schoenbrun 1945→1974 | tournament-list | yes |
| 2022-12-04 | `07f325d237` | add bend 2022 results | 7 | David Brown 1640→1684 | tournament-list | yes |
| 2023-01-01 | `6dc582074d` | add la-2022 results | 7 | Kolton Koehler 1842→1863 | tournament-list | yes |
| 2023-02-20 | `a94a0b427b` | add nola-2023 results | 33 | Wajid Iqbal 1339→1467 | tournament-list | yes |
| 2023-02-20 | `9f6310a50c` | add hood river 2023 results | 19 | Gunther Jacobi 1695→1614 | tournament-list | yes |
| 2023-04-04 | `834c3c87f8` | add austin 2023 results | 11 | Prashant Murti 1365→1210 | tournament-list | yes |
| 2023-04-19 | `5698be39c0` | add silverspring results | 8 | Joshua Castellano 1880→1905 | tournament-list | yes |
| 2023-05-06 | `f6f5848680` | slingerlands 2023 results | 18 | Brad Whitmarsh 1645→1704 | tournament-list | yes |
| 2023-06-10 | `38d40f8997` | Update all_rating.py with Austin one-day Jun 2023 | 6 | Chris Canik 1759→1927 | tournament-list | no |
| 2023-06-11 | `698366c261` | Update all_rating.py with St Louis Jun 2023 results | 4 | Jason Keller 1851→1885 | tournament-list | no |
| 2023-07-16 | `536d90f84d` | Update all_rating.py with seattle-jul2023 | 7 | Jesse Day 2043→2025 | tournament-list | no |
| 2023-08-12 | `fe9becfcc2` | Update all_rating.py with austin-aug2023 | 6 | Chris Canik 1927→1795 | tournament-list | no |
| 2023-08-12 | `47b7c23b6f` | Update all_rating.py with portland-aug2023 | 12 | Travis Chaney 1592→1614 | tournament-list | no |
| 2023-09-09 | `d08b0fa166` | Update all_rating.py with columbia-2023 | 10 | Sam Rosin 2054→1957 | tournament-list | no |
| 2023-10-22 | `31b7c55b35` | Update all_rating.py with potomac-oct2023 | 9 | Sam Rosin 1957→1896 | tournament-list | no |
| 2023-11-13 | `3e7a493118` | adding nacc-2023main as 11-11 to keep in sequence with next two | 38 | Eric Fox 1423→1218 | tournament-list | no |
| 2023-11-13 | `a8c0766ac9` | Update all_rating.py with nacc-2023playoffs as 11-12 | 7 | Kevin Fraley 1995→2017 | tournament-list | no |
| 2023-11-13 | `2c46e9b1ac` | Update all_rating.py with nacc-2023after for nacc afterword | 18 | John Karris 1470→1488 | tournament-list | no |
| 2023-11-14 | `aa9988a50c` | Update all_rating.py -- removing nacc changes -- needs rework due to errors | 40 | Eric Fox 1222→1423 | tournament-list | no |
| 2023-11-14 | `7de04210d5` | Update all_rating.py with nacc2023-d1 | 22 | Brad Whitmarsh 1704→1758 | tournament-list | no |
| 2023-12-11 | `9ef5fba181` | Update all_rating.py with palmsprings-dec2023 | 6 | Andrea Hatch 1096→1135 | tournament-list | no |
| 2024-03-02 | `0ce3b35a0e` | Update all_rating.py with portland-pub-mar2024 | 8 | Keith Valentine 1235→1277 | tournament-list | no |
| 2024-04-19 | `cabad2ed50` | Update all_rating.py with ATX and portland pub 3 and 4 | 32 | James Curley 1711→1560 | tournament-list | no |
| 2024-04-28 | `cffa1ba7ef` | Update all_rating.py with championscup-2024 | 23 | Robert Linn 1826→1677 | tournament-list | no |
| 2024-05-04 | `9fb6fbf95b` | Update all_rating.py with portlandpub-may2024 and correcting previous date | 21 | Joe Roberdeau 1140→1222 | tournament-list | no |
| 2024-05-28 | `24644eaa59` | Update all_rating.py with potomac-may2024 | 8 | Nitya Chagti 1393→1481 | tournament-list | no |
| 2024-05-28 | `9da563739b` | Update all_rating.py with seattle-may2024, correcting date on potomac-may2024 | 21 | Christopher Grubb 1723→1855 | tournament-list | no |
| 2024-06-15 | `a935c71f1a` | Update all_rating.py with     portlandpub-jun2024 | 9 | Gunther Jacobi 1712→1629 | tournament-list | no |
| 2024-07-20 | `f6e4c1a46e` | Update all_rating.py with portlandpub-jul2024 | 6 | Ruth Hamilton 1360→1405 | tournament-list | no |
| 2024-07-26 | `0f1bd05d2a` | Update all_rating.py with wordcup-2024-eb | 16 | Mike Johnson 1882→1707 | tournament-list | no |
| 2024-07-31 | `0e5b0b4ee0` | Update all_rating.py with wordcup-2024-d2 and wordcup-2024-d1 | 51 | Tony Boyle 626→918 | tournament-list | no |
| 2024-08-07 | `12294b94cb` | Update all_rating.py with glenhaven-2024 | 6 | Gary Smart 1488→1399 | tournament-list | no |
| 2024-08-25 | `8013f75cbb` | Update all_rating.py with portlandpub-aug2024 | 4 | Gunther Jacobi 1671→1729 | tournament-list | no |
| 2024-08-30 | `5f3bafe1af` | Update all_rating.py with pdxwords-eb-2024 | 8 | Jeannie Wilson 1096→1199 | tournament-list | no |
| 2024-09-02 | `a34b3b7472` | Update all_rating.py with lewes-2024 | 10 | Niel Gan 1143→1383 | tournament-list | no |
| 2024-09-02 | `4860cf5d8c` | Update all_rating.py with pdxwords-2024 | 18 | Kolton Koehler 1926→1859 | tournament-list | no |
| 2024-10-05 | `979259c8bc` | Update all_rating.py with portlandpub-oct2024 | 9 | Alec Sjöholm 1984→1923 | tournament-list | no |
| 2024-10-26 | `2690ca109a` | Update all_rating.py with seattle-oct262024 | 16 | Ather Sharif 1037→1222 | tournament-list | no |
| 2024-11-02 | `4d2a3983f7` | Update all_rating.py with columbia-2024 | 8 | Rob Robinsky 1882→1825 | tournament-list | no |
| 2024-11-03 | `cedbc3fe2d` | Update all_rating.py  with portlandpub-nov2024 | 6 | Kolton Koehler 1960→1937 | tournament-list | no |
| 2024-12-07 | `158f3ef22e` | Update all_rating.py with portlandpub-dec2024 | 6 | Conrad Bassett-Bouchard 1902→1874 | tournament-list | no |
| 2024-12-08 | `25ad2dbd35` | Update all_rating.py with sanfrancisco-dec2024 | 33 | John O'Laughlin 1716→1935 | tournament-list | no |
| 2024-12-15 | `3fb5972f09` | Update all_rating.py with vancouver-dec2024 | 16 | Evans Clinchy 1801→1916 | tournament-list | no |
| 2025-02-17 | `feb25fb34f` | Update all_rating.py with hood-river-2025 | 20 | Mark Francillon 1673→1470 | tournament-list | no |
| 2025-03-02 | `dbbef13448` | Update all_rating.py with providence-apr2025 | 4 | Matthew O'Connor 1877→2038 | tournament-list | no |
| 2025-04-05 | `52b9d27709` | Update all_rating.py with providence-05apr2025" | 6 | Richard Buck 1707→1562 | tournament-list | no |
| 2025-04-12 | `0f729a4375` | Update all_rating.py with portland-pub-12apr2025 | 10 | Gunther Jacobi 1618→1534 | tournament-list | no |
| 2025-04-13 | `36652167c8` | Update all_rating.py with portland-pub-13apr2025 | 9 | Keith Valentine 1190→1308 | tournament-list | no |
| 2025-04-20 | `cfd1590f97` | Update all_rating.py with championscup-2025 | 10 | Laurie Cohen 1804→1962 | tournament-list | no |
| 2025-05-04 | `5300c49493` | Update all_rating.py with rome-may2025 | 6 | Guy Ingram 1323→1297 | tournament-list | no |
| 2025-05-10 | `797075823f` | Update all_rating.py with bellingham-may2025 | 4 | Jennifer Clinchy 1393→1469 | tournament-list | no |
| 2025-05-26 | `fa8a6e1e7e` | Update all_rating.py with seattle-may2025 | 12 | Christopher Grubb 1939→1822 | tournament-list | no |
| 2025-06-08 | `91227ecacc` | Update all_rating.py with austin-atx2025 | 6 | Ben Weaver 1318→1250 | tournament-list | no |
| 2025-06-21 | `363c672efa` | Update all_rating.py | 6 | Julia Swaney 1150→988 | tournament-list | no |
| 2025-06-22 | `a286d32941` | Update all_rating.py with nova-jun2025 | 8 | Nitya Chagti 1445→1342 | tournament-list | no |
| 2025-07-13 | `5e626e068e` | Update all_rating.py with portlandpub-jun2025 | 4 | Will Anderson 2004→1971 | tournament-list | no |
| 2025-07-13 | `e75fdb34c4` | Update all_rating.py with bend-jun2025 | 6 | Travis Chaney 1638→1665 | tournament-list | no |
| 2025-08-01 | `400a81acb3` | Update all_rating.py with wordcup-2025-eb | 6 | Paula Catanese 1209→1290 | tournament-list | no |
| 2025-08-06 | `10a445a11d` | Update all_rating.py with wordcup-2025-d1 | 33 | Sammy Okosagah 1809→1970 | tournament-list | no |
| 2025-08-06 | `7da797377d` | Update all_rating.py with wordcup-2025-d2 | 28 | Ather Sharif 1190→1370 | tournament-list | no |
| 2025-08-29 | `a274920b8f` | Update all_rating.py with pdxwords-eb-2025 | 8 | Andrea Hatch 1178→1282 | tournament-list | no |
| 2025-08-30 | `209f6f32ff` | Update all_rating.py with slingerlands-series1-2025 | 6 | Terry Kang 1472→1495 | tournament-list | no |
| 2025-08-31 | `b69cfb879b` | adding slingerlands-series2-2025 | 8 | Stefan Rau 1753→1960 | tournament-list | no |
| 2025-09-01 | `0992ba94f5` | Update all_rating.py with pdxwords-2025 | 16 | Andrea Hatch 1282→1163 | tournament-list | no |
| 2025-10-05 | `20f2b1db3f` | Update all_rating.py with charlottesville-2025 | 14 | Marty Gold 1609→1457 | tournament-list | no |
| 2025-10-25 | `8f4d9705b7` | Update all_rating.py with seattle-oct252025 | 10 | John O'Laughlin 1956→1815 | tournament-list | no |
| 2025-10-26 | `8b8e909726` | Update all_rating.py with seattle-oct262025 | 10 | Carson Ip 1708→1598 | tournament-list | no |

## Detail: engine changes

### `da077423a3` skip rating games against the bye player
*2022-07-07 — Martin DeMello*  
python files: rating.py  

12 players' ratings changed:

| player | before | after | delta | deviation | games |
|---|---|---|---|---|---|
| Joe Roberdeau | 1391 | 1372 | -19 | 75.83→77.85 | 28 |
| Melissa Routzahn | 1605 | 1599 | -6 | 64.25→65.46 | 42 |
| Randi Goldberg | 1630 | 1624 | -6 | 61→61.51 | 48 |
| Rob Robinsky | 1978 | 1984 | +6 | 75.6→76.58 | 28 |
| Geoff Thevenot | 1933 | 1936 | +3 | 64.27→64.87 | 42 |
| Jason Keller | 1825 | 1828 | +3 | 94.97→96.93 | 14 |
| Brian Bowman | 1857 | 1859 | +2 | 64.1→64.69 | 42 |
| Chris Lipe | 1855 | 1857 | +2 | 50.08→50.65 | 76 |
| David Whitley | 1913 | 1915 | +2 | 40.2→40.35 | 123 |
| Becky Dyer | 1712 | 1711 | -1 | 44.25→44.44 | 102 |
| Evans Clinchy | 1887 | 1888 | +1 | 38.31→38.44 | 137 |
| Wolfram Poh | 1765 | 1766 | +1 | 94.93→96.89 | 14 |

### `906445ab82` skip forfeit losses for rating purposes
*2022-07-08 — Martin DeMello*  
python files: rating.py  

1 players' ratings changed:

| player | before | after | delta | deviation | games |
|---|---|---|---|---|---|
| Winter | 1780 | 1798 | +18 | 95.03→97.17 | 14 |

### `546051b407` Apply rating deviation adjustment in the PlayerDB adjust_tournament method
*2024-03-10 — jvc56*  
python files: all_rating.py  

150 players' ratings changed (showing 15):

| player | before | after | delta | deviation | games |
|---|---|---|---|---|---|
| Jesse Day | 1996 | 1838 | -158 | 35.72→86.01 | 159 |
| David Whitley | 1853 | 1708 | -145 | 23.98→75.43 | 361 |
| Betty Cornelison | 1223 | 1107 | -116 | 28.84→97.85 | 246 |
| Alec Sjöholm | 2006 | 1894 | -112 | 33.6→78.89 | 190 |
| Sandy Nang | 1445 | 1557 | +112 | 34.84→80.59 | 165 |
| Ben Schoenbrun | 1956 | 1852 | -104 | 35.16→82.58 | 163 |
| Matt Canik | 1715 | 1615 | -100 | 77.4→118.24 | 27 |
| Sammy Okosagah | 1943 | 2040 | +97 | 56.52→111.75 | 59 |
| Christopher Grubb | 1814 | 1723 | -91 | 35.41→79.08 | 160 |
| Nitya Chagti | 1302 | 1393 | +91 | 41.08→84.25 | 121 |
| Evan Berofsky | 1895 | 1805 | -90 | 51.02→85.88 | 71 |
| Jesse Matthews | 1801 | 1891 | +90 | 54.86→85.66 | 60 |
| Robert Linn | 1737 | 1826 | +89 | 40.72→81.55 | 121 |
| Joshua Castellano | 1918 | 2002 | +84 | 33.23→81.44 | 186 |
| Lindsay Shin | 1486 | 1568 | +82 | 55.89→77.3 | 60 |

### `c5aa5ff05a` Read the chronological list of tournaments from a csv file
*2025-11-16 — Martin DeMello*  
python files: all_rating.py, tournaments.py  
**Also touched data/ or results/ — the change is not purely code.**  

78 players' ratings changed (showing 15):

| player | before | after | delta | deviation | games |
|---|---|---|---|---|---|
| Michael McKenna | 1635 | 1641 | +6 | 90.09→85.13 | 48 |
| Adam Logan | 2087 | 2089 | +2 | 114.44→114.36 | 7 |
| Chris Patrick Morgan | 1345 | 1347 | +2 | 118.02→117.63 | 6 |
| Dave Wiegand | 2058 | 2060 | +2 | 77→77.53 | 658 |
| Lisa Mueller | 1544 | 1546 | +2 | 96.35→96.23 | 14 |
| Lisa Odom | 1858 | 1860 | +2 | 99.95→99.92 | 15 |
| Matt Zeleznik | 1689 | 1687 | -2 | 108.69→108.05 | 12 |
| Paula Catanese | 1311 | 1313 | +2 | 62.34→62.39 | 260 |
| Steve Pellinen | 1658 | 1660 | +2 | 93.71→93.52 | 29 |
| Terry Kang | 1453 | 1451 | -2 | 71.97→73.06 | 312 |
| Abdul Khan | 1226 | 1225 | -1 | 73.68→73.65 | 62 |
| Alec Sjöholm | 2069 | 2070 | +1 | 75.61→76.08 | 435 |
| Andrea Hatch | 1163 | 1164 | +1 | 75.82→75.55 | 175 |
| Anne Hopkins | 874 | 875 | +1 | 150 | 6 |
| Ather Sharif | 1375 | 1374 | -1 | 80.27→81.06 | 118 |


## Not replayable

These commits' trees could not produce a ratings list. The oldest predate the history replay entirely (no `process_old_results`).

| date | commit | subject | reason |
|---|---|---|---|
| 2021-07-30 | `e70c04688b` | convert to py3 and format with blue | no entry point |
| 2021-07-30 | `11ef7441a3` | refactor .tou file parsing | no entry point |
| 2021-07-30 | `1d23bb9da4` | refactor player and player list code | no entry point |
| 2021-08-02 | `091f71b47f` | clean up some formatting of comments | no entry point |
| 2021-08-02 | `9b93b90eef` | remove some stuff that is not needed in python3 | no entry point |
| 2021-08-02 | `8ae112d26b` | pull ratings file parsing into its own class | no entry point |
| 2021-08-02 | `4317e4d38b` | pull out exception message formatting into a function | no entry point |
| 2021-08-02 | `df1f3a1d7b` | move ratings calculations to their own class | no entry point |
| 2021-08-03 | `d50432de50` | rework tou file parsing and game result representation | no entry point |
| 2021-08-03 | `c1eea6890a` | fix minor errors, get sample data outputting correctly | no entry point |
| 2021-08-03 | `b9c912827c` | add a basic unit test for the tou parser | no entry point |
| 2021-08-03 | `5fb45c39c6` | fix some issues caught by pylint | no entry point |
| 2021-08-03 | `03146627c8` | fix import bug | no entry point |
| 2021-08-03 | `3753e53fc6` | split on whitespace, not space | no entry point |
| 2021-08-03 | `d4493ae7aa` | add pretty printing of game results | no entry point |
| 2021-08-03 | `b4eaec24b6` | snake case the world | no entry point |
| 2021-08-03 | `dd0e2e79d2` | use python logging | no entry point |
| 2021-08-03 | `fb5f5d7acc` | set initial rating to manual seed if rated opponent average is too low | no entry point |
| 2021-08-03 | `0ff0daf83d` | add basic ratings calculation tests | no entry point |
| 2021-09-06 | `606a39869f` | add csv results and ratings file support | no entry point |
| 2021-09-09 | `357ce121d7` | add usage help and sample files | no entry point |
| 2021-11-02 | `ef51cf6732` | add gui frontend | no entry point |
| 2021-11-02 | `ed90a829c9` | parse a ratings csv with just two columns | no entry point |
| 2021-11-03 | `90198e8030` | tweak layout a bit | no entry point |
| 2021-11-03 | `83975dde00` | fix for extraneous newlines in csv output on windows | no entry point |
| 2022-03-16 | `4c9b851bc3` | add a script to rate all the tournaments in the results dir | no entry point |
| 2022-03-16 | `4e88a5bb89` | add a persistent player database | no entry point |
| 2022-03-17 | `baf3697e7b` | fix call to csv writer | no entry point |
| 2022-03-17 | `fa777e4519` | treat initial ratings of < 100 as unrated players | no entry point |
| 2022-03-18 | `bb9187846e` | add a gui to all_ratings to rate a new tournament | no entry point |
| 2022-03-18 | `71726bf9f6` | write current ratings to csv | no entry point |
| 2023-05-06 | `483f1ab28a` | Update all_rating.py | KeyError: 'austin-may-2023' |
| 2023-05-29 | `8ac319933f` | Update all_rating.py | KeyError: 'moco-2023-results' |
| 2023-05-30 | `a172d7ee08` | Update all_rating.py | KeyError: 'moco-2023-results' |
| 2023-08-06 | `57332b3bdb` | Update all_rating.py with vancouver-aug2023 | KeyError: 'vancouver-aug2023' |
| 2023-09-16 | `8c74253df5` | Update all_rating.py with austin-sep2023 | KeyError: 'austin-sep2023' |
| 2023-09-30 | `4156acc7b4` | Update all_rating.py with seattle-sept2023 | KeyError: 'seattle-sept2023' |
| 2023-10-08 | `14399e922c` | Update all_rating.py with riorancho-oct2023 | KeyError: 'riorancho-oct2023' |
| 2023-10-29 | `d144aaf7b9` | Update all_rating.py with texasstate-2023 | KeyError: 'texasstate-2023' |
| 2023-11-04 | `9dd525be4a` | Update all_rating.py with portland-nov2023 | KeyError: 'portland-nov2023' |
| 2023-11-14 | `4e8b6e430d` | Update all_rating.py with nacc2023-d2 | KeyError: 'nacc2023-d2' |
| 2023-11-14 | `8cfa7ebf6d` | Update all_rating.py with nacc2023-d1p (playoff) | KeyError: 'nacc2023-d1p' |
| 2023-11-14 | `25055cbbde` | Update all_rating.py with nacc2023-d2p | KeyError: 'nacc2023-d2p' |
| 2023-11-14 | `94d5aa94bf` | Update all_rating.py with nacc2023-after | KeyError: 'nacc2023-after' |
| 2023-11-14 | `9247f431c3` | Update all_rating.py -- changing nacc2023-after to nacc2023-afterword | KeyError: 'nacc2023-after' |
| 2024-01-15 | `e97690ea30` | Update all_rating.py with nola-open-2024 and nola-lite-2024 | no entry point |
| 2024-01-15 | `4d45675c0b` | Update all_rating.py to correct previous check in, left off dates | no entry point |
| 2024-01-20 | `5a79eac143` | Update all_rating.py with portland_pub-jan2024 | KeyError: 'portland_pub-jan2024' |
| 2024-01-20 | `eb27570d27` | Update all_rating.py -- changing portland_pub-jan2024 to portland-pub-jan2024 | KeyError: 'portland-pub-jan2024' |
| 2024-02-19 | `22559bf70b` | Update all_rating.py with hood-river-2024 | KeyError: 'hood-river-2024' |
| 2024-10-27 | `693f68ccdf` | Update all_rating.py with seattle-oct272024 | KeyError: 'seattle-oct272024' |
| 2025-01-20 | `e6eb540a8a` | Update all_rating.py with nola-lite-2025 and nola-open-2025 | Exception: |
| 2025-02-17 | `4641ffd53c` | Update all_rating.py -- correcting nola-open-2025 date | Exception: |
| 2026-03-25 | `51bdda4a8a` | Add Player and Rating models with migrations | no entry point |
| 2026-03-25 | `cebed4b333` | Add public search and player detail views (no-JS) | no entry point |
| 2026-03-25 | `bd1ab72846` | Add manage admin section with player and rating CRUD | no entry point |
| 2026-03-25 | `3ac82e0862` | Add import_csv management command | no entry point |
| 2026-03-25 | `d73940d8b3` | Add CSV import admin UI | no entry point |
| 2026-03-25 | `58dfd628c9` | Fix N+1 query on current_rating | no entry point |
| 2026-03-25 | `2a74cdcb6f` | Fix possibly-unbound errors variable in import_csv handle() | no entry point |
| 2026-03-25 | `05fb42f520` | Fix all ruff lint and formatting issues | no entry point |
| 2026-03-25 | `e0aa48b7a2` | Add whitenoise for serving static files in production | no entry point |
| 2026-03-25 | `1d6cca28d8` | Add CSRF_TRUSTED_ORIGINS setting for production HTTPS | no entry point |
| 2026-03-25 | `8efc8694eb` | Improve search: combine icontains with trigram word similarity | no entry point |
| 2026-03-25 | `58c5202d4f` | Hide results list when a specific player is selected (no-JS flow) | no entry point |
| 2026-04-02 | `217f9f25e1` | Use exact matching only if we have a prefix of a player's name | no entry point |