#!/usr/bin/env python3
"""装箱计算 CLI 入口。

Usage:
    python cartonize.py input.json
    echo '{"order_id": "...", ...}' | python cartonize.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# 确保 scripts/ 目录在 sys.path 中
_scripts_dir = Path(__file__).resolve().parent
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

from cartonization_engine.models import CartonizationRequest
from cartonization_engine.engine import CartonizationEngine


def main() -> None:
    # 读取输入 JSON
    if len(sys.argv) > 1:
        input_path = Path(sys.argv[1])
        if not input_path.exists():
            print(f"错误: 文件不存在 {input_path}", file=sys.stderr)
            sys.exit(1)
        raw = input_path.read_text(encoding="utf-8")
    elif not sys.stdin.isatty():
        raw = sys.stdin.read()
    else:
        print("用法: python cartonize.py input.json", file=sys.stderr)
        print("  或: echo '{...}' | python cartonize.py", file=sys.stderr)
        sys.exit(1)

    try:
        request = CartonizationRequest.model_validate_json(raw)
    except Exception as e:
        print(f"输入解析失败: {e}", file=sys.stderr)
        sys.exit(1)

    engine = CartonizationEngine()
    result = engine.cartonize(request)

    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
