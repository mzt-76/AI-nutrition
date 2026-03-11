#!/usr/bin/env bash
# Copy reference table data from dev to prod Supabase project.
# Reads DATABASE_URL from ".env dev" (source) and ".env prod" (target).
# Uses psql \copy (client-side CSV) — works through pooler connections.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# Read DATABASE_URL from .env files
source_url=$(grep '^DATABASE_URL=' "$ROOT_DIR/.env dev" | cut -d= -f2-)
target_url=$(grep '^DATABASE_URL=' "$ROOT_DIR/.env prod" | cut -d= -f2-)

if [[ -z "$source_url" || -z "$target_url" ]]; then
  echo "ERROR: Could not read DATABASE_URL from .env files"
  exit 1
fi

TABLES=("recipes" "openfoodfacts_products" "ingredient_mapping")
TMP_DIR="/tmp/supabase_seed"
mkdir -p "$TMP_DIR"

for table in "${TABLES[@]}"; do
  echo "=== $table ==="
  csv="$TMP_DIR/$table.csv"

  # Export from dev
  echo "  Exporting from dev..."
  psql "$source_url" -c "\copy public.$table TO '$csv' WITH CSV HEADER"
  rows=$(( $(wc -l < "$csv") - 1 ))
  echo "  → $rows rows exported"

  # Import to prod
  echo "  Importing to prod..."
  psql "$target_url" -c "\copy public.$table FROM '$csv' WITH CSV HEADER"
  echo "  ✓ Done"
done

# Verify counts
echo ""
echo "=== Verification ==="
for table in "${TABLES[@]}"; do
  count=$(psql "$target_url" -t -c "SELECT count(*) FROM public.$table;")
  echo "  $table: $count rows"
done

# Cleanup
rm -rf "$TMP_DIR"
echo "Done."
