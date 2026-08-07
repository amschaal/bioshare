#!/bin/bash

# Run this every hour or so in cron to purge idle requests.

PGUSER=postgres
PGDATABASE=bioshare
THRESHOLD_IDLE=20
THRESHOLD_IDLE_IN_XACT=10
THRESHOLD_TOTAL=100
LOGFILE="/var/log/postgres_idle_monitor.log"

# Get counts from pg_stat_activity
IFS='|' read -r TOTAL IDLE IDLE_XACT  <<< $(psql -U "$PGUSER" -d "$PGDATABASE" -Atc "
SELECT
    count(*) as total,
    count(*) FILTER (WHERE state = 'idle') as idle,
    count(*) FILTER (WHERE state = 'idle in transaction') as idle_in_xact
FROM pg_stat_activity;
")

echo "$(date): Total=$TOTAL Idle=$IDLE IdleInXact=$IDLE_XACT" >> "$LOGFILE"

# Check thresholds and purge if necessary
if [[ "$IDLE" -gt "$THRESHOLD_IDLE" ]] || [[ "$IDLE_XACT" -gt "$THRESHOLD_IDLE_IN_XACT" ]] || [[ "$TOTAL" -gt "$THRESHOLD_TOTAL" ]];
then
  TERMINATED_COUNT=$(psql -U "$PGUSER" -d "$PGDATABASE"  -Atc "
    SELECT COUNT(*) FROM (
      SELECT pg_terminate_backend(pid) AS terminated
      FROM pg_stat_activity
      WHERE state = 'idle'
        AND state_change < NOW() - INTERVAL '1 hour'
        AND pid <> pg_backend_pid()
    ) AS sub
    WHERE terminated = true;
  ")

 # Output the result
 echo "Terminated $TERMINATED_COUNT idle connection(s) older than 1 hour." >> "$LOGFILE"

else
    echo "$(date): Connection counts are within normal limits." >> "$LOGFILE"
fi