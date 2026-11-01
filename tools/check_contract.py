#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""契约检查：te_man_open 复刻版 vs 原版真机 introspection 数据。

逐节点比对：INPUT_TYPES（参数名/顺序/类型/枚举/默认值/min-max-step/tooltip）、
RETURN_TYPES/RETURN_NAMES、CATEGORY/FUNCTION/OUTPUT_NODE。
零依赖（纯标准库），无 ComfyUI/torch 也能跑。

用法：python3 tools/check_contract.py
"""

import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
GOLDEN = os.path.join(REPO, "spec", "_introspection", "te_man_introspection.json")


def norm(x):
    """tuple<->list 归一化后可比较。"""
    if isinstance(x, (list, tuple)):
        return [norm(i) for i in x]
    if isinstance(x, dict):
        return {str(k): norm(v) for k, v in x.items()}
    return x


def main():
    with open(GOLDEN, encoding="utf-8") as f:
        gold = json.load(f)

    import te_man_open as pkg

    mine_nodes = pkg.NODE_CLASS_MAPPINGS
    missing = [r for r in gold["nodes"] if r not in mine_nodes]
    extra = [r for r in mine_nodes if r not in gold["nodes"]]
    failures = []

    for reg in sorted(gold["nodes"]):
        if reg not in mine_nodes:
            continue
        g = gold["nodes"][reg]
        cls = mine_nodes[reg]
        diffs = []

        # INPUT_TYPES
        try:
            mine_it = norm(cls.INPUT_TYPES())
            gold_it = norm(g["INPUT_TYPES"]["value"])
            if mine_it != gold_it:
                # 输出差异详情
                for sect in ("required", "optional", "hidden"):
                    a, b = gold_it.get(sect) or {}, (mine_it.get(sect) or {})
                    for k in sorted(set(a) | set(b)):
                        if k not in a:
                            diffs.append(f"[{sect}] 多余参数 {k}")
                        elif k not in b:
                            diffs.append(f"[{sect}] 缺少参数 {k}")
                        elif a[k] != b[k]:
                            diffs.append(f"[{sect}] {k} 不一致:\n    期望 {json.dumps(a[k], ensure_ascii=False)[:200]}\n    实际 {json.dumps(b[k], ensure_ascii=False)[:200]}")
        except Exception as e:  # noqa: BLE001
            diffs.append(f"INPUT_TYPES 调用失败: {type(e).__name__}: {e}")

        # 元数据
        for attr in ("RETURN_TYPES", "RETURN_NAMES", "CATEGORY", "FUNCTION"):
            gv, mv = g.get(attr), getattr(cls, attr, None)
            if gv is not None and norm(gv) != norm(mv):
                diffs.append(f"{attr}: 期望 {gv!r} 实际 {mv!r}")
        if g.get("OUTPUT_NODE") is not None and bool(g["OUTPUT_NODE"]) != bool(getattr(cls, "OUTPUT_NODE", False)):
            diffs.append(f"OUTPUT_NODE: 期望 {g['OUTPUT_NODE']!r} 实际 {getattr(cls, 'OUTPUT_NODE', None)!r}")

        if diffs:
            failures.append((reg, diffs))

    # 显示名映射
    dn_fail = [r for r, v in gold["node_display_name_mappings"].items()
               if pkg.NODE_DISPLAY_NAME_MAPPINGS.get(r) != v]

    print("=" * 64)
    print(f"原版节点: {len(gold['nodes'])}  复刻注册: {len(mine_nodes)}")
    if missing:
        print(f"缺少注册 ({len(missing)}): {missing}")
    if extra:
        print(f"多余注册 ({len(extra)}): {extra}")
    if dn_fail:
        print(f"显示名不一致 ({len(dn_fail)}): {dn_fail}")
    for reg, diffs in failures:
        print(f"\n✗ {reg}")
        for d in diffs:
            print("   " + d)
    if not missing and not extra and not failures and not dn_fail:
        print("\n✅ 契约检查全部通过")
        return 0
    print(f"\n❌ 契约检查未通过: {len(failures)} 个节点有差异")
    return 1


if __name__ == "__main__":
    sys.exit(main())
