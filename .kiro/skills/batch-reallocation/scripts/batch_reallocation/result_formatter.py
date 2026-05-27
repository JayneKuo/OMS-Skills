from __future__ import annotations

from batch_reallocation.models import ExecuteResponse


def format_execution_result(result: ExecuteResponse) -> dict:
    return {
        "submitted_orders": result.submitted_orders,
        "succeeded_orders": result.succeeded_orders,
        "partial_succeeded_orders": result.partial_succeeded_orders,
        "failed_orders": result.failed_orders,
        "skipped_orders": result.skipped_orders,
        "warnings": result.warnings,
    }
