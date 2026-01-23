# Bangkok Event Discovery App

## Overview

A web app to discover **real** small-medium events in Bangkok that are hard to find through mainstream channels - underground parties, rooftop sessions, pop-up dinners, and more.

**Important**: This app scrapes real events from Instagram, Facebook, and web sources. It does NOT use fake/sample data.

## Quick Start

### 1. Prerequisites
- Docker & Docker Compose
- Node.js 18+
- Python 3.11+

### 2. Start Database

```bash
# Start PostgreSQL with PostGIS
docker-compose up -d db redis
```

### 3. Run Scrapers (REQUIRED - populates real events)

```bash
cd scrapers
pip install -r requirements.txt
python run_scrapers.py
```

This will scrape real events from:
- Instagram hashtags (#bangkokparty, #bangkokunderground, etc.)
- Facebook event pages
- Eventbrite and Meetup

### 4. Start Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API available at http://localhost:8000

### 5. Start Frontend

```bash
cd frontend
npm install
npm run dev
```

App available at http://localhost:3000

### 6. Add Mapbox Token (for map view)

Get a free token at https://mapbox.com and add to `frontend/.env.local`:

```
NEXT_PUBLIC_MAPBOX_TOKEN=pk.your_token_here
```

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    Scrapers     │────▶│    PostgreSQL   │◀────│    Backend      │
│  (IG, FB, Web)  │     │    + PostGIS    │     │    (FastAPI)    │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                                                         ▼
                                                ┌─────────────────┐
                                                │    Frontend     │
                                                │    (Next.js)    │
                                                └─────────────────┘
```

## Event Sources

### Primary: Instagram
- Hashtags: #bangkokparty #bangkokunderground #thonglornightlife
- Focuses on underground/mid-sized events not on mainstream platforms
- Scrapes public posts only

### Secondary: Facebook
- Public event pages and searches
- Bangkok event organizers and venues

### Tertiary: Web
- Eventbrite Bangkok events
- Meetup Bangkok groups

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/events` | List events with filters |
| GET | `/api/events/{id}` | Get event details |
| POST | `/api/events/submit` | Submit new event |
| POST | `/api/scraper/run` | Trigger manual scrape |
| GET | `/api/scraper/status` | Check scraper status |

### Filter Parameters

```
GET /api/events?district=Thonglor&category=party&q=techno
```

- `lat`, `lng`, `radius_km` - Location-based filter
- `district` - District filter (Sukhumvit, Thonglor, etc.)
- `category` - Category (party, music, art, food, etc.)
- `start_date`, `end_date` - Date range
- `q` - Full-text search
- `featured_only` - Only featured events

## Districts Covered

- **Sukhumvit**: Thonglor, Ekkamai, Phrom Phong, Asok
- **Central**: Siam, Silom, Sathorn
- **Others**: Bangna, Ari, Ratchada

## Project Structure

```
event_party_app/
├── frontend/               # Next.js 14 app
│   ├── app/               # App router pages
│   ├── components/        # React components
│   └── lib/               # API client
│
├── backend/               # FastAPI backend
│   └── app/
│       ├── api/           # API routes
│       ├── models/        # SQLAlchemy models
│       ├── schemas/       # Pydantic schemas
│       └── services/      # Business logic
│
├── scrapers/              # Event scrapers
│   ├── scrapers/          # IG, FB, Web scrapers
│   ├── processors/        # Event parsing
│   └── run_scrapers.py    # Main entry point
│
└── database/
    └── init.sql           # Schema (no fake data)
```

## Running Scrapers Automatically

### Option 1: Enable in Backend

Set `ENABLE_SCRAPER=true` to run scrapers automatically every 4 hours:

```bash
ENABLE_SCRAPER=true uvicorn app.main:app --reload
```

### Option 2: Manual Trigger

```bash
curl -X POST http://localhost:8000/api/scraper/run
```

### Option 3: Cron Job

Add to crontab to run every 4 hours:

```bash
0 */4 * * * cd /path/to/scrapers && python run_scrapers.py
```

## Deployment

### Frontend (Vercel)

```bash
cd frontend
vercel
```

### Backend (Railway/Render)

Deploy with environment variables:
- `DATABASE_URL` - PostgreSQL connection string
- `ENABLE_SCRAPER` - Set to `true` for auto-scraping

## Environment Variables

### Backend
```
DATABASE_URL=postgresql://user:pass@host:5432/db
REDIS_URL=redis://localhost:6379/0
ENABLE_SCRAPER=false
```

### Frontend
```
NEXT_PUBLIC_API_URL=http://localhost:8000/api
NEXT_PUBLIC_MAPBOX_TOKEN=pk.your_token
```

## Troubleshooting

### No events showing
1. Make sure you ran the scrapers: `python run_scrapers.py`
2. Check database has events: `SELECT COUNT(*) FROM events WHERE status='approved'`
3. Check backend is running: http://localhost:8000/api/events

### Map not loading
1. Add Mapbox token to `frontend/.env.local`
2. Restart frontend

### Scraper not finding events
- Instagram/Facebook have rate limits - wait and retry
- Check network connectivity
- Run with debug logging: `DEBUG=true python run_scrapers.py`

## License

MIT
