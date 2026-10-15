#!/usr/bin/env bash
# Beat 8.5. Kill the worker mid refund and prove exactly one refund row.
#
# This is the whole point of Beat 8. If it ever fails, a crash has started
# paying customers twice.
set -euo pipefail

ORDER_ID="ord_C1_07"
AMOUNT=1000

count_refunds() {
  uv run python -c "
from sqlalchemy import func, select
from ops_agent.db.models import Refund
from ops_agent.db.session import session_scope
with session_scope() as s:
    print(s.scalar(select(func.count()).select_from(Refund).where(Refund.order_id == '$ORDER_ID')))
"
}

cleanup() { pkill -9 -f ops_agent.workflows.worker || true; }
trap cleanup EXIT

echo "seeding"
uv run python -c "from ops_agent.db.seed import seed; seed()" > /dev/null

echo "worker up, with a 20 second pause inside the refund"
REFUND_ACTIVITY_DELAY_SECONDS=20 uv run python -m ops_agent.workflows.worker &
sleep 5

echo "starting the refund"
uv run python -m ops_agent.workflows.start "$ORDER_ID" "$AMOUNT" > /dev/null 2>&1 &
sleep 5

echo "killing the worker mid refund"
pkill -9 -f ops_agent.workflows.worker

after_crash=$(count_refunds)
echo "rows right after the crash: $after_crash"

if [ "$after_crash" != "1" ]; then
  echo "FAILED, the kill landed outside the dangerous window, test proved nothing"
  exit 1
fi

echo "waiting 35s for Temporal to give up on the dead attempt"
sleep 35

echo "restarting the worker"
uv run python -m ops_agent.workflows.worker &
sleep 20

final=$(count_refunds)
echo "rows after the retry: $final"

if [ "$final" != "1" ]; then
  echo "FAILED, expected exactly 1 refund row, got $final"
  exit 1
fi

echo "passed, exactly one refund row survived the crash"
