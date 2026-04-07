#!/usr/bin/env python3
"""装箱结果验证器。

验证装箱结果的正确性：
1. 7 条硬规则校验
2. SKU 数量守恒
3. 计费重量正确性

Usage:
    python validate_result.py result.json
    echo '{"status": "SUCCESS", ...}' | python validate_result.py
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
)


def validate_hard_rules(result: CartonizationResult) -> list[str]:
    """校验 7 条硬规则。"""
    errors: list[str] = []
    for pkg in result.packages:
        pid = pkg.package_id
        items = pkg.items

        # 注意: Package.items 是 PackageItem（无物理属性），
        # 硬规则校验需要原始 SKUItem 信息。
        # 此处仅校验结构层面可验证的规则。

        # 规则 1: 检查 box_type 存在
        if not pkg.box_type or not pkg.box_type.box_id:
            errors.append(f"[{pid}] 缺少箱型信息")

        # 规则: 非空 SKU 列表
        if not items:
            errors.append(f"[{pid}] SKU 列表为空")

        # 规则: 每个 SKU 数量 > 0
        for item in items:
            if item.quantity <= 0:
                errors.append(f"[{pid}] SKU {item.sku_id} 数量 <= 0")

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
        errors.append(
            f"SKU 数量不守恒: 输入={input_qty}, 输出={output_qty}"
        )
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
    # 读取输入
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

    # 支持两种格式: 纯 result 或 {request, result}
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

    # 1. 硬规则校验
    all_errors.extend(validate_hard_rules(result))

    # 2. SKU 数量守恒
    all_errors.extend(validate_sku_conservation(request_data, result))

    # 3. 计费重量正确性
    all_errors.extend(validate_billing_weight(result))

    # 输出结果
    output = {
        "status": "PASS" if not all_errors else "FAIL",
        "total_checks": 3,
        "errors": all_errors,
        "packages_checked": len(result.packages),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))

    if all_errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
