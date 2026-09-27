# scraping-pipeline

A polite, validated web scraping pipeline in Python. It collects structured data from the two public sandboxes built for practising scraping, [books.toscrape.com](https://books.toscrape.com) and [quotes.toscrape.com](https://quotes.toscrape.com), and shows the techniques that real projects need:

| Technique | Where |
|---|---|
| Pagination (following "next" links) | `sites/books.py`, `sites/quotes.py --mode html` |
| Listing page -> detail pages, in parallel threads | `sites/books.py` |
| JavaScript-rendered page, data extracted from the embedded JSON (no browser) | `quotes --mode js` |
| Infinite scroll: calling the hidden JSON API directly | `quotes --mode api` |
| Real headless browser (Playwright) when nothing else works | `quotes --mode browser` |
| Retries with exponential backoff (429/5xx), timeouts | `http.py` |
| Global rate limit shared by all threads, robots.txt check | `http.py` |
| Disk cache so re-runs do not hit the site again | `http.py` |
| Data validation: required fields, ranges, types, duplicates, empty-field rates | `validate.py` |
| Export to Excel (.xlsx, locale-proof), CSV, JSON and SQLite | `export.py` |
| 31 offline tests (saved HTML fixtures + local HTTP server) | `tests/` |

## Quick start

```bash
pip install -r requirements.txt

python -m scrapekit books                    # 1000 books, 50 pages -> data/books.csv/.json/.db
python -m scrapekit books --max-pages 2      # quick run: 40 books
python -m scrapekit quotes --mode api        # 100 quotes via the JSON API
python -m scrapekit quotes --mode html
python -m scrapekit quotes --mode js

# optional: real browser
pip install playwright && playwright install chromium
python -m scrapekit quotes --mode browser --max-pages 2
```

Every run prints a validation report before writing files:

```
=== validation ===
rows: 1000
duplicates: 0
RESULT: PASS

1000 rows in 530.4s | 1051 requests, 0 from cache
wrote data/books.csv
```

Use `--strict` in scheduled jobs: the exit code becomes 2 when validation fails, so a silent layout change on the site is caught immediately instead of producing an empty dataset.

## Options

| Option | Default | Meaning |
|---|---|---|
| `--max-pages N` | all | stop after N listing pages |
| `--workers N` | 4 | parallel detail-page downloads (books) |
| `--delay S` | 0.5 | minimum seconds between requests, across all threads |
| `--formats` | xlsx,csv,json,sqlite | output formats |
| `--cache DIR` | .cache | HTML cache; `--cache ""` disables it |
| `--strict` | off | exit code 2 on validation failure |

## Output fields

**books**: upc, title, category, price_incl_tax, price_excl_tax, tax, in_stock, rating (1-5), reviews, description, image_url, url

**quotes**: text, author, tags, author_url

## Design notes

- Site modules never call `requests` directly; they receive a `Fetcher`. The tests pass a fake one that serves saved HTML, so the parsing logic is tested without a network.
- Parsers are pure functions `html -> records`, which makes them easy to test and to reuse with the Playwright output.
- One failing detail page is logged and skipped; it never kills a 1000-page crawl.
- The three quote modes are tested to return identical data.

## Tests

```bash
pip install pytest
python -m pytest -q
```

## Responsible use

Both target sites exist specifically for scraping practice. On other sites, read the terms of service and robots.txt, keep the rate limit low, identify your client in the User-Agent, and do not collect personal data you have no right to process.

## License

MIT
