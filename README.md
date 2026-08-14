# Five Finger Finds

Five Finger Finds is a static, public-safe buyer-decision-tool site for Five Finger Supplies.

It is designed for $0 incremental operation:

- GitHub Pages hosting for the static site
- GitHub Actions scheduled build, validation, maintenance, and deploy
- Python standard-library build scripts
- Browser-native JavaScript calculators
- No paid APIs, no paid hosting, no customer accounts, no checkout, no inventory, no fulfillment, no support queue

## Monetization status

Affiliate monetization is enabled with the public Amazon Associates tracking tag configured in `data/affiliate.json`.

The generator will not guess an affiliate tag. Product recommendation cards use structured, source-backed search phrases and do not rehost Amazon Program Content, reviews, star ratings, prices, availability, or images.

## Local build

```powershell
python scripts/build.py --out site
python scripts/validate.py --dist site
python -m unittest discover -s tests
```

## Search verification files

Place public site-verification files such as `google123abc.html` or `BingSiteAuth.xml` in `static-root/`. The build copies non-hidden files from that folder into the deployed site root so URL-prefix verification can find them under `https://5iv3fingersupplies-co.github.io/five-finger-finds/`.

## Optimization loop

The `Optimization Report` workflow runs weekly and on manual dispatch. It performs a $0 deterministic analysis of page structure, source coverage, recommendation slots, category depth, and content gaps, then writes a Markdown summary into the GitHub Actions run summary.

Private performance exports can be analyzed locally without committing them. Put optional CSV exports in gitignored `private-inputs/` using any of these names:

- `search-console-pages.csv`
- `search-console-queries.csv`
- `bing-pages.csv`
- `bing-queries.csv`
- `amazon-associates.csv`

Then run:

```powershell
python scripts/optimize.py --out reports
```

The report ranks pages and topics by likely next-best work. It does not call paid APIs, does not require analytics scripts, and does not publish private export data.

## Public safety

This repository is meant to contain only static-site code, public source records, templates, and generated output rules. Do not commit `.env` files, API keys, private JARVIS/core code, browser profiles, logs, customer data, or private company documents.
