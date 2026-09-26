-- ============================================================================
-- Shiptivity analytics -- Module 3: Analyse the latest feature releases
-- ----------------------------------------------------------------------------
-- Run with:   sqlite3 ./shiptivity.db < answer.sql
-- Data set:  2018-02-03 -> 2019-02-01 (UTC), 100 users, 200 cards
-- Release:    the Kanban board went live on 2018-06-02 (README + first
--             card_change_history event), so every question is answered
--             with a "before" (day < 2018-06-02) and an "after" period.
-- All *_timestamp columns are unix epoch seconds, rendered as UTC dates.
-- ============================================================================


-- ===========================================================================
-- PART 1: Daily average users BEFORE and AFTER the feature change
-- ===========================================================================

-- 1a. One row per calendar day with the number of daily active users.
--     A recursive date spine is used so days without any login are returned
--     as 0 instead of silently disappearing from the average.
--     Columns: day, daily_active_users, sessions, period(before|after)

WITH RECURSIVE
  bounds AS (
    SELECT date(min(login_timestamp), 'unixepoch') AS first_day,
           date(max(login_timestamp), 'unixepoch') AS last_day
    FROM login_history
  ),
  calendar(day) AS (
    SELECT first_day FROM bounds
    UNION ALL
    SELECT date(day, '+1 day') FROM calendar, bounds
    WHERE day < bounds.last_day
  ),
  daily AS (
    SELECT date(login_timestamp, 'unixepoch') AS day,
           COUNT(DISTINCT user_id)            AS daily_active_users,
           COUNT(*)                           AS sessions
    FROM login_history
    GROUP BY day
  )
SELECT
  calendar.day                                                        AS day,
  COALESCE(daily.daily_active_users, 0)                               AS daily_active_users,
  COALESCE(daily.sessions, 0)                                         AS sessions,
  CASE WHEN calendar.day < '2018-06-02' THEN 'before' ELSE 'after' END AS period
FROM calendar
LEFT JOIN daily ON daily.day = calendar.day
ORDER BY calendar.day;


-- 1b. The before/after averages the first graph is built from.
--     Columns: period, days, avg_daily_active_users, avg_sessions_per_day,
--              peak_daily_active_users, distinct_users_in_period

WITH RECURSIVE
  bounds AS (
    SELECT date(min(login_timestamp), 'unixepoch') AS first_day,
           date(max(login_timestamp), 'unixepoch') AS last_day
    FROM login_history
  ),
  calendar(day) AS (
    SELECT first_day FROM bounds
    UNION ALL
    SELECT date(day, '+1 day') FROM calendar, bounds
    WHERE day < bounds.last_day
  ),
  daily AS (
    SELECT date(login_timestamp, 'unixepoch') AS day,
           COUNT(DISTINCT user_id)            AS daily_active_users,
           COUNT(*)                           AS sessions
    FROM login_history
    GROUP BY day
  ),
  per_day AS (
    SELECT
      calendar.day                                                        AS day,
      COALESCE(daily.daily_active_users, 0)                               AS daily_active_users,
      COALESCE(daily.sessions, 0)                                         AS sessions,
      CASE WHEN calendar.day < '2018-06-02' THEN 'before' ELSE 'after' END AS period
    FROM calendar
    LEFT JOIN daily ON daily.day = calendar.day
  ),
  period_users AS (
    SELECT
      CASE WHEN date(login_timestamp, 'unixepoch') < '2018-06-02'
           THEN 'before' ELSE 'after' END       AS period,
      COUNT(DISTINCT user_id)                   AS distinct_users
    FROM login_history
    GROUP BY period
  )
SELECT
  p.period,
  COUNT(*)                                     AS days,
  ROUND(AVG(p.daily_active_users), 2)          AS avg_daily_active_users,
  ROUND(AVG(p.sessions), 2)                    AS avg_sessions_per_day,
  MAX(p.daily_active_users)                    AS peak_daily_active_users,
  u.distinct_users                             AS distinct_users_in_period
FROM per_day p
JOIN period_users u ON u.period = p.period
GROUP BY p.period, u.distinct_users
ORDER BY CASE p.period WHEN 'before' THEN 0 ELSE 1 END;


-- ===========================================================================
-- PART 2: Number of status changes by card
-- ===========================================================================

-- 2a. One row per card. card_change_history also stores the row that CREATED
--     the card (oldStatus IS NULL, 1 row per card, not a user action), so
--     status_changes counts only real, user driven moves.
--     Columns: card_id, card_name, status_changes, card_created_events,
--              total_events, last_change, first_status_change

SELECT
  h.cardID                                                        AS card_id,
  COALESCE(c.name, '(unknown card)')                              AS card_name,
  SUM(CASE WHEN h.oldStatus IS NULL THEN 0 ELSE 1 END)            AS status_changes,
  SUM(CASE WHEN h.oldStatus IS NULL THEN 1 ELSE 0 END)            AS card_created_events,
  COUNT(*)                                                        AS total_events,
  date(MAX(h.timestamp), 'unixepoch')                             AS last_change,
  MIN(CASE WHEN h.oldStatus IS NULL THEN NULL
           ELSE date(h.timestamp, 'unixepoch') END)               AS first_status_change
FROM card_change_history h
LEFT JOIN card c ON c.id = h.cardID
GROUP BY h.cardID
ORDER BY status_changes DESC, last_change DESC, h.cardID;


-- 2b. Shape of the distribution: how many cards were moved 0, 1, 2 ... times.
--     Columns: status_changes, number_of_cards

SELECT
  status_changes,
  COUNT(*) AS number_of_cards
FROM (
  SELECT cardID,
         SUM(CASE WHEN oldStatus IS NULL THEN 0 ELSE 1 END) AS status_changes
  FROM card_change_history
  GROUP BY cardID
)
GROUP BY status_changes
ORDER BY status_changes;


-- 2c. Where the cards are moving to (shows back-and-forth / rework).
--     Columns: from_status, to_status, moves

SELECT
  COALESCE(oldStatus, '(card created)') AS from_status,
  newStatus                             AS to_status,
  COUNT(*)                              AS moves
FROM card_change_history
GROUP BY oldStatus, newStatus
ORDER BY moves DESC;
