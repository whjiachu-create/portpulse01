#!/bin/bash
set -euo pipefail

# Check if DATABASE_URL is set
if [[ -z "${DATABASE_URL:-}" ]]; then
    echo "Error: DATABASE_URL environment variable is not set" >&2
    exit 1
fi

set +H

echo "=== PortPulse Database Index Verification ==="
echo "DATABASE_URL: ${DATABASE_URL}"
echo

# Function to check if query uses Index Only Scan
check_index_scan() {
    local query_name="$1"
    local query="$2"
    local expected_index="$3"
    
    echo "Checking: $query_name"
    echo "Expected index: $expected_index"
    echo "Query: $query"
    echo
    
    # Run EXPLAIN ANALYZE BUFFERS and capture output
    explain_output=$(psql "$DATABASE_URL" -X -q -t -c "EXPLAIN (ANALYZE, BUFFERS) $query" 2>&1)
    echo "$explain_output"
    echo
    
    # Check if Index Only Scan was used
    if echo "$explain_output" | grep -q "Index Only Scan using $expected_index"; then
        echo "✅ PASS: Using expected index '$expected_index'"
    else
        echo "⚠️  WARNING: Not using expected index '$expected_index' (Index Only Scan)"
        # Print warning in yellow
        echo -e "\033[33mPlease check if the query is using the correct index and consider optimizing.\033[0m"
    fi
    echo
    echo "----------------------------------------"
    echo
}

# Query 1: port_snapshots for latest record of a port
check_index_scan \
    "Latest port snapshot" \
    "SELECT * FROM port_snapshots WHERE unlocode = 'USLAX' ORDER BY timestamp DESC LIMIT 1" \
    "idx_snapshots_unloc_ts_cover"

# Query 2: port_dwell for last 14 days
check_index_scan \
    "Port dwell for last 14 days" \
    "SELECT * FROM port_dwell WHERE unlocode = 'USLAX' AND date >= CURRENT_DATE - INTERVAL '14 days'" \
    "idx_dwell_unloc_date_cover"

echo "Verification complete."