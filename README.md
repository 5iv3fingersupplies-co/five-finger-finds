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

## Public safety

This repository is meant to contain only static-site code, public source records, templates, and generated output rules. Do not commit `.env` files, API keys, private JARVIS/core code, browser profiles, logs, customer data, or private company documents.
