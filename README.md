# RetailIQ — Retail People Analytics

Real-time people counting and zone tracking powered by Google Cloud Vision AI, Supabase, and Vercel.

## Architecture

```
Camera (local machine)
       │
       ▼  every 3 s
 Python backend ──► Google Vision API
       │
       ▼
   Supabase (cloud PostgreSQL + Realtime)
       │
       ▼
 React Dashboard (Vercel) ◄── live websocket push
```

No server required between the camera and the dashboard — Supabase is the data layer.

## Supabase Setup (one-time)

1. Go to [supabase.com](https://supabase.com) → **New project**
2. Open **SQL Editor → New query**, paste the contents of `supabase/schema.sql`, click **Run**
3. Go to **Project Settings → API**, copy:
   - **Project URL** → used in both `.env` files
   - **anon / public key** → frontend `.env`
   - **service_role key** → backend `.env` (keep secret)

## Backend Setup (camera machine)

```bash
cd backend
cp .env.example .env
# Fill in GOOGLE_VISION_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_KEY, CAMERA_SOURCE

python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

pip install -r requirements.txt
python main.py
```

### Camera source values

| Source            | Value                                              |
|-------------------|----------------------------------------------------|
| Built-in webcam   | `0`                                                |
| Second webcam     | `1`                                                |
| RTSP stream       | `rtsp://admin:pass@192.168.1.100:554/stream`       |
| HTTP MJPEG        | `http://192.168.1.100:8080/video`                  |

## Frontend Setup (local dev)

```bash
cd frontend
cp .env.example .env
# Fill in VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY

npm install
npm run dev    # http://localhost:3000
```

## Vercel Deployment

The frontend is deployed at Vercel and reads from Supabase directly via the anon key.

1. Import the `retailiq` GitHub repo at [vercel.com/new](https://vercel.com/new)
2. Set **Root Directory** → `frontend`
3. Add environment variables:
   - `VITE_SUPABASE_URL`
   - `VITE_SUPABASE_ANON_KEY`
4. Deploy

## Project Structure

```
retailiq/
├── backend/
│   ├── .env.example      ← copy to .env and fill in
│   ├── config.py         ← loads env vars
│   ├── main.py           ← entry point
│   ├── camera.py         ← OpenCV frame capture
│   ├── vision_api.py     ← Google Vision REST call
│   ├── detector.py       ← 3-second detection loop
│   ├── supabase_db.py    ← Supabase insert
│   └── requirements.txt
├── frontend/
│   ├── .env.example      ← copy to .env and fill in
│   ├── vercel.json
│   ├── vite.config.js
│   ├── package.json
│   └── src/
│       ├── supabase.js          ← Supabase client
│       ├── App.jsx              ← main app + realtime subscription
│       ├── App.css
│       └── components/
│           ├── LiveCount.jsx    ← updates via Supabase Realtime
│           ├── HourlyChart.jsx  ← bar chart
│           ├── ZoneHeatmap.jsx  ← left/centre/right bars
│           └── StatsPanel.jsx   ← daily summary
└── supabase/
    └── schema.sql         ← paste into Supabase SQL Editor
```

## Dashboard Features

| Widget | Data source | Update frequency |
|---|---|---|
| Live Count | `detections` table (Realtime) | Instant (websocket push) |
| Hourly Chart | `hourly_today` view | Every 30 s |
| Zone Heatmap | `zone_totals_today` view | Every 30 s |
| Today's Summary | `stats_today` view | Every 30 s |
