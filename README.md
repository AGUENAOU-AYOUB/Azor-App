# Azor Price Updater Webapp

This repository contains tools to update Shopify variant prices and now includes a small web application to run them more easily.

## Running the Web Application

1. Install dependencies (Flask, python-dotenv, and requests):
   ```bash
   pip install -r requirements.txt
   ```
2. Copy `.env.example` to `.env` and fill in all placeholders:
   ```
   SHOP_DOMAIN=azorjewelry.myshopify.com
   API_TOKEN=shpat_xxx_REPLACE_ME_xxx
   API_VERSION=2024-04
   ADMIN_USERNAME=youruser
   ADMIN_PASSWORD=yourpass
   SECRET_KEY=random-string
   ```
3. Start the server (set `DEBUG=true` in your environment to enable Flask debug
   mode):
   ```bash
   python run_webapp.py
   ```
4. Visit `http://localhost:5000` and log in with the credentials above.

## Background Worker

The updater scripts now run in a small asynchronous job queue. The worker
thread starts automatically when the web server launches, so no extra setup is
required.

## Using the Updaters

- **Percentage Updater** adjusts prices by a percentage and uses `scripts/update_prices_shopify.py`. Enter the desired percentage and monitor the real-time log while the script runs. The script now retries automatically if the Shopify API responds with HTTP `429 Too Many Requests`.
- **Variant Updater** runs `tempo solution/update_prices.py`. The page shows all surcharges from `tempo solution/variant_prices.json`. Edit the values for each chain and click **Save Changes** to update the file. Then use the **Run Update** button to apply the prices while the real-time log streams. Both updaters now rely on Shopify's GraphQL bulk API behind the scenes for faster processing.
- **Bulk Updater** reads `scripts/bulk_payload.json` and runs `scripts/bulk_update_prices.py` to perform a GraphQL bulk mutation updating all listed variants. Start it from the Bulk page in the web interface.

`bulk_payload.json` should contain objects with `id` and `price` fields, for example:

```json
[
  {"id": 1234567890, "price": "19.99"},
  {"id": 9876543210, "price": "24.50"}
]
```

The output from each script is streamed live to your browser so you can follow progress.

### Backup file

When `update_prices_shopify.py` runs for the first time it downloads every
variant price from Shopify and stores them in a file named
`shopify_backup.json` under `scripts/`. This allows
`reset_prices_shopify.py` to restore the original prices later.  The backup can
grow to around **500&nbsp;KB** depending on the number of variants, so it is now
ignored by Git and will be recreated whenever needed.

## Deploying in Production

1. Install the dependencies (only required once):
   ```bash
   pip install -r requirements.txt
   ```
2. Set the necessary environment variables. You can copy `.env.example` to `.env` or configure them in your hosting platform.
3. Start the server with Gunicorn:
   ```bash
    gunicorn run_webapp:app -b 0.0.0.0:8000
    ```

## Running Tests

To run the automated tests you'll need the packages listed in
`requirements.txt` **and** the `pytest` framework:

```bash
pip install -r requirements.txt pytest
```

Then execute the tests with:

```bash
python -m pytest
```
