# Cartonization Skill — 装箱计算引擎

基于规则分组 + FFD 启发式算法的装箱计算工具，支持严格物理装箱和规则建议两种模式。

## 快速开始

```bash
# 安装依赖
pip install pydantic>=2.0

# 执行装箱计算
python scripts/cartonize.py input.json

# 验证装箱结果
python scripts/validate_result.py result.json

# 运行测试
pip install pytest hypothesis
pytest tests/ -v
```

## 目录结构

```
cartonization/
├── SKILL.md                          # Agent 指令（装箱规则、两种模式、5步流程）
├── README.md                         # 本文件
├── references/
│   ├── 需求规格.md                    # 完整装箱需求（V2）
│   └── 数据契约.md                    # SKU/箱型/承运商字段定义
├── scripts/
│   ├── cartonize.py                  # 装箱计算 CLI 入口
│   ├── validate_result.py            # 装箱结果验证器
│   └── cartonization_engine/         # 核心代码包（13个模块）
│       ├── models.py                 # 数据模型（Pydantic v2）
│       ├── engine.py                 # 流水线编排入口
│       ├── validator.py              # 输入验证 + L1/L2/L3 分级
│       ├── pre_grouper.py            # 预分组（温区/危险品/禁混/易碎重物拆组）
│       ├── sorter.py                 # FFD 排序
│       ├── packer.py                 # FFD 装箱
│       ├── box_selector.py           # 箱型选择（含单件尺寸校验）
│       ├── splitter.py              # 多包拆分
│       ├── fill_rate_checker.py      # 填充率校验
│       ├── hard_rule_checker.py      # 7条硬规则校验
│       ├── billing_calculator.py     # 计费重计算
│       ├── oversize_handler.py       # 超大件处理
│       └── fallback_handler.py       # 4级回退处理
└── tests/
    ├── conftest.py                   # 共享 fixtures
    ├── test_properties.py            # Property 1-2, 25-26
    ├── test_props_pregrouper.py      # Property 3-7（预分组）
    ├── test_props_ffd.py             # Property 8-9（FFD）
    ├── test_props_box_selector.py    # Property 10-12（箱型选择）
    ├── test_props_splitter.py        # Property 13-14（拆分）
    ├── test_props_fill_rate.py       # Property 15-16（填充率）
    ├── test_props_hard_rules.py      # Property 17-20（硬规则）
    ├── test_props_billing.py         # Property 21（计费重）
    ├── test_props_engine.py          # Property 22-23（引擎）
    └── test_props_fallback.py        # Property 24（回退）

## 核心能力

1. 7 条硬规则自动校验（温区隔离、危险品隔离、超重超尺寸、禁混、易碎防震、液体防漏）
2. 软规则分组优化（易碎品与重物自动拆组、赠品同包）
3. 单件尺寸校验（支持旋转判断，120cm 灯管不会塞进 40cm 箱子）
4. FFD 启发式装箱算法
5. 计费重计算（max(实际重量, 体积重量)，向上取整到 0.1kg）
6. 4 级失败回退（非标箱→虚拟箱→大件专线→人工介入）
7. 输入完整度分级（L1 规则建议 / L2 估算 / L3 严格装箱）
8. 26 个属性测试覆盖全部正确性属性

## 输入格式

见 [references/数据契约.md](references/数据契约.md)

## 使用方式

Agent 可以：
- 直接运行 `scripts/cartonize.py` 执行严格装箱（L3 模式）
- 按 SKILL.md 中的规则建议模式处理自然语言输入（L1 模式）
- 运行 `scripts/validate_result.py` 验证装箱结果
- 运行 `pytest tests/ -v` 验证代码正确性
```
