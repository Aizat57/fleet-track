# FleetTrack

Fleet management (Django) — vehicles, drivers, insurance & road tax renewals, breakdowns and maintenance,
expenses, documents, notifications and reports. White-and-blue glass UI ("Glassy Dashboard V2").

## Run (this computer)
Double-click `jalankan.bat`, then open http://localhost:8000

## Setup on a new computer
```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env          # then fill in DJANGO_SECRET_KEY
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py createsuperuser
.venv\Scripts\python.exe manage.py runserver
```

Optional, **empty database only** (training/demo): `.venv\Scripts\python.exe manage.py seed_demo`.
It refuses to run once any vehicle exists, so it can never mix sample figures into real data.

Not stored in git: `db.sqlite3`, `media/` (vehicle photos), `private_media/` (documents) and `.env`. Back up all four.

## Roles
Two groups are created by migration. Assign users in **Admin › Users**:
- **Fleet Manager** — full access, including uploading and opening documents.
- **Fleet Viewer** — read-only; cannot open stored documents.

Every page, action and file download checks permissions on the server. Documents live in `private_media/`
and are only served through a permission-checked view.

## How figures are calculated
- Insurance / road tax status always comes from the latest recorded expiry date per vehicle. A renewal adds a
  new period; history is kept. "Expiring soon" = within 30 days (`FLEET_EXPIRY_WARNING_DAYS`).
- Fleet counts exclude Archived, Sold and Disposed vehicles.
- Spend = expenses marked Paid or Outstanding. Forecast entries are shown separately and never counted.
- Unknown costs are left blank and shown as "not recorded" — never RM 0.00.
- Notifications are computed live from the data; only read/unread state is stored.

## Code map
- `fleet/models.py` — data model (audit trail via django-simple-history)
- `fleet/alerts.py` — "Needs Your Attention" / notification engine
- `fleet/finance.py` — period handling and expense aggregation
- `fleet/views/` — one module per area
- `fleet/templatetags/ui.py` — icons, badges, RM formatting, form fields
- `static/css/fleettrack.css` — design tokens and all components
- `static/js/app.js`, `static/js/charts.js` — UI behaviour and dependency-free charts

## Tests
```powershell
.venv\Scripts\python.exe manage.py test fleet
```
