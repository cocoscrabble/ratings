Rating software for CoCo tournaments.

The ratings are based on the Norwegian system; see docs/norwegian-rating.pdf.

Sample input and output files can be found under testdata/

### Usage

```
usage: rating.py [-h] [--name NAME] [--date DATE] [--rating-file RATING_FILE] [--result-file RESULT_FILE]

optional arguments:
  -h, --help            show this help message and exit
  --name NAME           Tournament name
  --date DATE           Tournament date (yyyy-mm-dd)
  --rating-file RATING_FILE
                        Ratings file
  --result-file RESULT_FILE
                        Results file
```

### Input format

The script can accept data in several formats.

**Ratings**

Ratings can be entered in one of two formats:
- csv: See `testdata/loco-ratings.csv`
- RT: See `testdata/20200217_HoodRiver.RT`

**Results**

Tournament data can likewise be entered in two formats:
- csv: See `testdata/loco21.csv`
- tou: See `testdata/hoodriver.tou`

The `.RT` and `.tou` formats are provided to support other programs that use
them; if you are entering the data yourself `.csv` is an easier format to
produce, e.g. by exporting from Excel or a Google Sheets document. Note that
the files must be named with the correct extension since the script uses the
extension to determine what format they are in.

If you are using the `.csv` results format, you need to supply a tournament
name and date as well (`.tou` files have the tournament details included).

### Output format

The results and new ratings are output in two formats, `output.txt` and
`output.csv`. The `.txt` file is easy to read and print out; the `.csv` file
can be imported into a spreadsheet app.

### Example

```
python rating.py --rating-file testdata/loco-ratings.csv --result-file testdata/loco21.csv --name "LOCO 2021" --date 2021-09-06
```
