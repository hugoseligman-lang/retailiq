-- ─────────────────────────────────────────────────────────────
-- RetailIQ — Supabase schema
-- Paste this into Supabase > SQL Editor > New query > Run
-- ─────────────────────────────────────────────────────────────

-- 1. Main table
CREATE TABLE IF NOT EXISTS detections (
  id           BIGSERIAL PRIMARY KEY,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  people_count INTEGER      NOT NULL,
  zone_left    INTEGER      NOT NULL DEFAULT 0,
  zone_center  INTEGER      NOT NULL DEFAULT 0,
  zone_right   INTEGER      NOT NULL DEFAULT 0
);

-- 2. Row-Level Security
ALTER TABLE detections ENABLE ROW LEVEL SECURITY;

-- Anonymous users can read (dashboard)
CREATE POLICY "anon_read" ON detections
  FOR SELECT USING (true);

-- Service-role key (backend script) can insert
CREATE POLICY "service_insert" ON detections
  FOR INSERT WITH CHECK (true);

-- 3. View: hourly breakdown for today (used by dashboard chart)
CREATE OR REPLACE VIEW hourly_today AS
SELECT
  to_char(created_at AT TIME ZONE 'UTC', 'HH24') AS hour,
  MAX(people_count)                               AS peak_count,
  ROUND(AVG(people_count)::NUMERIC, 1)            AS avg_count,
  COUNT(*)                                        AS samples
FROM detections
WHERE created_at::DATE = CURRENT_DATE
GROUP BY hour
ORDER BY hour;

-- 4. View: zone totals for today
CREATE OR REPLACE VIEW zone_totals_today AS
SELECT
  COALESCE(SUM(zone_left),   0) AS total_left,
  COALESCE(SUM(zone_center), 0) AS total_center,
  COALESCE(SUM(zone_right),  0) AS total_right
FROM detections
WHERE created_at::DATE = CURRENT_DATE;

-- 5. View: daily summary stats
CREATE OR REPLACE VIEW stats_today AS
SELECT
  COALESCE(MAX(people_count), 0) AS peak_count,
  COALESCE(SUM(people_count), 0) AS total_detections,
  COALESCE(
    (
      SELECT to_char(created_at AT TIME ZONE 'UTC', 'HH24') || ':00'
      FROM   detections
      WHERE  created_at::DATE = CURRENT_DATE
      GROUP  BY to_char(created_at AT TIME ZONE 'UTC', 'HH24')
      ORDER  BY AVG(people_count) DESC
      LIMIT  1
    ),
    'N/A'
  ) AS peak_hour
FROM detections
WHERE created_at::DATE = CURRENT_DATE;

-- 6. Enable Realtime on detections (for live count updates)
ALTER PUBLICATION supabase_realtime ADD TABLE detections;
