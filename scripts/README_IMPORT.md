# Import inventory via API

`import_inventory_via_api.py` populates the database by calling the backend API:

1. **Products** from `products_list.csv` (dedupes by product_name, sets product_type PH or TB for iPads)
2. **Suppliers** from unique `Source` values in `inventory_units.csv` (creates UnitAcquisitionSource with source_type SU)
3. **Inventory units** from `inventory_units.csv` (excludes Colour and Grade; cost_of_unit=0; skips duplicate IMEI/serial or unknown product_name)

## Requirements

- Python 3.7+
- `requests`: `pip install requests`

## Usage

From the **backend** repo root:

```bash
# Default: API_BASE=Render URL, admin/6foot7foot, CSVs from ../affordable-gadgets-frontend/
python scripts/import_inventory_via_api.py
```

With custom API and CSV paths:

```bash
export API_BASE=https://affordable-gadgets-backend.onrender.com
export API_USERNAME=admin
export API_PASSWORD=6foot7foot
export CSV_DIR=/path/to/folder/containing/csvs
# Or set each file explicitly:
# export PRODUCTS_CSV=/path/to/products_list.csv
# export UNITS_CSV=/path/to/inventory_units.csv
python scripts/import_inventory_via_api.py
```

For **local** backend:

```bash
export API_BASE=http://127.0.0.1:8000
python scripts/import_inventory_via_api.py
```

## CSV format

- **products_list.csv**: headers `product_name`, `Brand`, `Model`
- **inventory_units.csv**: must include `product_name`, `IMEI`, `Serial Number`, `Selling Price`, `Condition`, `Date`, `Source`, `RAM (GB)`, `Storage (GB)`. Colour and Grade are ignored. Date format: `DD-MM-YY` (e.g. `02-01-26`)

## Security

Do not commit real passwords. Use environment variables or a local `.env` that is gitignored.
