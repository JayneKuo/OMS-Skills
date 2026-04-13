#!/usr/bin/env python3
"""装箱结果验证器。

验证装箱结果的正确性：
1. 硬规则校验（结构层 + 完整 SKU 数据层）
2. SKU 数量守恒
3. 计费重量正确性

Usage:
    python validate_result.py result.json
    echo '{"request": {...}, "result": {...}}' | python validate_result.py
"""

from __future__ import annotations

import json
import sys
from decimal import Decimal, ROUND_CEILING
from pathlib import Path

_scripts_dir = Path(__file__).resolve().parent
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

from cartonization_engine.models import (
    CartonizationResult,
    CartonizationRequest,
    CartonStatus,
    HazmatType,
    SKUItem,
)
from cartonization_engine.hard_rule_checker import HardRuleChecker


def validate_hard_rules(result: CartonizationResult) -> list[str]:
    """校验结构层硬规则。"""
    errors: list[str] = []
    for pkg in result.packages:
        pid = pkg.package_id
        items = pkg.items
        if not pkg.box_type or not pkg.box_type.box_id:
            errors.append(f"[{pid}] 缺少箱型信息")
        if not items:
            errors.append(f"[{pid}] SKU 列表为空")
        for item in items:
            if item.quantity <= 0:
                errors.append(f"[{pid}] SKU {item.sku_id} 数量 <= 0")
    return errors


def validate_hard_rules_with_sku_data(
    result: CartonizationResult,
    request: CartonizationRequest,
) -> list[str]:
    """使用原始 SKU 数据做完整硬规则校验。"""
    errors: list[str] = []
    checker = HardRuleChecker()
    sku_map: dict[str, SKUItem] = {it.sku_id: it for it in request.items}

    for pkg in result.packages:
        # 重建 SKUItem 列表
        sku_items: list[SKUItem] = []
        for pi in pkg.items:
            ref = sku_map.get(pi.sku_id)
            if ref:
                sku_items.append(ref.model_copy(update={"quantity": pi.quantity}))

        if not sku_items:
            continue

        violations = checker.check(sku_items, pkg.box_type, request.carrier_limits)
        for v in violations:
            errors.append(f"[{pkg.package_id}] {v.rule_name}: {v.description}")

    return errors


def validate_sku_conservation(
    request_json: dict | None, result: CartonizationResult
) -> list[str]:
    """校验 SKU 数量守恒。"""
    if request_json is None:
        return ["跳过 SKU 守恒校验: 未提供原始请求"]
    if result.status != CartonStatus.SUCCESS:
        return []
    errors: list[str] = []
    input_qty: dict[str, int] = {}
    for item in request_json.get("items", []):
        sid = item.get("sku_id", "")
        input_qty[sid] = input_qty.get(sid, 0) + item.get("quantity", 0)
    output_qty: dict[str, int] = {}
    for pkg in result.packages:
        for pi in pkg.items:
            output_qty[pi.sku_id] = output_qty.get(pi.sku_id, 0) + pi.quantity
    if input_qty != output_qty:
        errors.append(f"SKU 数量不守恒: 输入={input_qty}, 输出={output_qty}")
    return errors


def validate_billing_weight(result: CartonizationResult) -> list[str]:
    """校验计费重量正确性。"""
    errors: list[str] = []
    for pkg in result.packages:
        bw = pkg.billing_weight
        if bw.billing_weight < bw.actual_weight:
            errors.append(
                f"[{pkg.package_id}] 计费重 {bw.billing_weight} < 实际重 {bw.actual_weight}"
            )
        if bw.billing_weight < bw.volumetric_weight:
            errors.append(
                f"[{pkg.package_id}] 计费重 {bw.billing_weight} < 体积重 {bw.volumetric_weight}"
            )
    return errors


def main() -> None:
    if len(sys.argv) > 1:
        input_path = Path(sys.argv[1])
        if not input_path.exists():
            print(f"错误: 文件不存在 {input_path}", file=sys.stderr)
            sys.exit(1)
        raw = input_path.read_text(encoding="utf-8")
    elif not sys.stdin.isatty():
        raw = sys.stdin.read()
    else:
        print("用法: python validate_result.py result.json", file=sys.stderr)
        sys.exit(1)

    data = json.loads(raw)

    if "status" in data:
        result_data = data
        request_data = None
    elif "result" in data:
        result_data = data["result"]
        request_data = data.get("request")
    else:
        print("错误: 无法识别输入格式", file=sys.stderr)
        sys.exit(1)

    try:
        result = CartonizationResult.model_validate(result_data)
    except Exception as e:
        print(f"结果解析失败: {e}", file=sys.stderr)
        sys.exit(1)

    all_errors: list[str] = []
    total_checks = 3

    # 1. 结构层硬规则校验
    all_errors.extend(validate_hard_rules(result))

    # 1.5 完整硬规则校验（如果有原始请求）
    if request_data is not None:
        try:
            request = CartonizationRequest.model_validate(request_data)
            full_rule_errors = validate_hard_rules_with_sku_data(result, request)
            all_errors.extend(full_rule_errors)
            total_checks += 1
        except Exception:
            pass  # 无法解析请求，跳过完整校验

    # 2. SKU 数量守恒
    all_errors.extend(validate_sku_conservation(request_data, result))

    # 3. 计费重量正确性
    all_errors.extend(validate_billing_weight(result))

    output = {
        "status": "PASS" if not all_errors else "FAIL",
        "total_checks": total_checks,
        "errors": all_errors,
        "packages_checked": len(result.packages),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))

    if all_errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
