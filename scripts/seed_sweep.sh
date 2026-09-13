#!/usr/bin/env bash
# Run the synthetic loop over several task-set seeds and summarize.  Usage: scripts/seed_sweep.sh 5
set -euo pipefail
N="${1:-5}"; cd "$(dirname "$0")/.."; source .venv/bin/activate; set -a; source .env; set +a
for s in $(seq 0 $((N-1))); do
  mkdir -p "out/sweep_$s"
  python -u run_demo.py --synthetic --no-viz --no-llm --seed "$s" --out "out/sweep_$s" > "out/sweep_$s/log.txt" 2>&1 && echo "seed $s done"
done
python scripts/seed_summary.py $(for s in $(seq 0 $((N-1))); do echo "out/sweep_$s"; done)
