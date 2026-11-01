#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TE_MAN 节点动态 introspection 脚本。

在 Windows + ComfyUI 环境下运行（GitHub Actions windows-latest 或本地），
把 TE_MAN 包的所有 pyd 模块真正 import 起来，导出每个 ComfyUI 节点的：

- NODE_CLASS_MAPPINGS / NODE_DISPLAY_NAME_MAPPINGS / WEB_DIRECTORY
- 每个节点类：FUNCTION / CATEGORY / OUTPUT_NODE / RETURN_TYPES / RETURN_NAMES /
  DESCRIPTION / DEPRECATED / EXPERIMENTAL / SEARCH_ALIASES / docstring /
  INPUT_TYPES() 完整返回（参数名、类型、选项列表、默认值）/ 方法 docstring
- 每个模块：docstring、模块级常量（含 URL、默认值、混淆常量原文）、
  类清单、函数 docstring、导入失败原因

输出单个 JSON 文件，用于回填 spec/ 里的"未确认"项。

用法：
    python introspect_te_man.py --comfyui <ComfyUI 目录> --out te_man_introspection.json

环境变量：COMFYUI_DIR（等价 --comfyui）。
"""

import argparse
import importlib
import json
import os
import platform
import sys
import traceback

MAX_STR = 30000  # 单个字符串常量最大保留长度（系统提示词很长，需要保留全文）
CONST_REPR_LIMIT = 4000  # 复合类型常量的 repr 超过此长度则跳过


# ---------------------------------------------------------------- JSON 安全化

def jsafe(obj, depth=0):
    """把任意 Python 对象转成 JSON 可序列化结构。"""
    if depth > 6:
        return repr(obj)[:500]
    if obj is None or isinstance(obj, (bool, int, float)):
        return obj
    if isinstance(obj, str):
        return obj[:MAX_STR]
    if isinstance(obj, bytes):
        return obj.decode("utf-8", "replace")[:MAX_STR]
    if isinstance(obj, dict):
        return {str(k): jsafe(v, depth + 1) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [jsafe(v, depth + 1) for v in obj]
    return repr(obj)[:1000]


def safe_call(fn):
    """安全调用无参函数，返回 {'ok': True, 'value': ...} 或 {'ok': False, 'error': ...}。"""
    try:
        return {"ok": True, "value": jsafe(fn())}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def doc_of(obj):
    d = getattr(obj, "__doc__", None)
    if isinstance(d, str) and d.strip():
        return d.strip()[:MAX_STR]
    return None


# ---------------------------------------------------------------- 节点类导出

NODE_ATTRS = (
    "FUNCTION", "CATEGORY", "OUTPUT_NODE", "RETURN_TYPES", "RETURN_NAMES",
    "DESCRIPTION", "DEPRECATED", "EXPERIMENTAL", "SEARCH_ALIASES",
    "NOT_IDEMPOTENT", "OUTPUT_TOOLTIPS", "LIST_INPUTS",
)


def introspect_node_class(cls):
    info = {
        "class": getattr(cls, "__name__", str(cls)),
        "module": getattr(cls, "__module__", None),
        "doc": doc_of(cls),
    }
    for attr in NODE_ATTRS:
        if hasattr(cls, attr):
            try:
                info[attr] = jsafe(getattr(cls, attr))
            except Exception as e:  # noqa: BLE001
                info[attr] = f"<error: {e}>"
    for flag in ("IS_CHANGED", "VALIDATE_INPUTS", "on_execute", "check_lazy_status"):
        info[f"has_{flag}"] = hasattr(cls, flag)
    if hasattr(cls, "INPUT_TYPES"):
        info["INPUT_TYPES"] = safe_call(cls.INPUT_TYPES)
    # 方法 docstring（Cython 编译后 docstring 仍在，信息量大）
    method_docs = {}
    for name in dir(cls):
        if name.startswith("_"):
            continue
        try:
            member = getattr(cls, name)
        except Exception:  # noqa: BLE001
            continue
        if callable(member):
            d = doc_of(member)
            if d:
                method_docs[name] = d
    if method_docs:
        info["method_docs"] = method_docs
    return info


# ---------------------------------------------------------------- 模块导出

SKIP_MEMBER_TYPES = ("module", "type")
CALLABLE_DOC = {}


def introspect_module(mod):
    info = {
        "module": getattr(mod, "__name__", None),
        "file": getattr(mod, "__file__", None),
        "doc": doc_of(mod),
    }
    constants = {}
    classes = {}
    function_docs = {}
    for name in dir(mod):
        if name.startswith("__") and name not in ("__version__",):
            continue
        try:
            value = getattr(mod, name)
        except Exception:  # noqa: BLE001
            continue
        vtype = type(value).__name__
        if vtype in SKIP_MEMBER_TYPES:
            if vtype == "type":
                d = doc_of(value)
                classes[name] = {"doc": d, "module": getattr(value, "__module__", None)}
            continue
        if callable(value):
            d = doc_of(value)
            if d:
                function_docs[name] = d
            continue
        if isinstance(value, (bool, int, float)) or (
            isinstance(value, str) and len(value) <= MAX_STR
        ):
            constants[name] = value
        elif isinstance(value, bytes):
            constants[name] = value.decode("utf-8", "replace")[:MAX_STR]
        elif isinstance(value, (list, tuple, dict)) and len(repr(value)) < CONST_REPR_LIMIT:
            constants[name] = jsafe(value)
    if constants:
        info["constants"] = constants
    if classes:
        info["classes"] = classes
    if function_docs:
        info["function_docs"] = function_docs
    return info


# ---------------------------------------------------------------- torch.cuda 桩

def patch_torch_cuda_stub():
    """CPU 环境下模拟一个 GPU。

    TE_MAN 的生成器模块在 import 时无条件调用 torch.cuda.current_device() 等
    （真实运行环境必有 GPU）。introspection 只需要 import 成功并读取
    INPUT_TYPES/RETURN_TYPES，不会真正执行 CUDA 运算，因此打桩即可。
    """
    try:
        import torch
    except ImportError:  # noqa: BLE001
        return
    cuda = torch.cuda
    try:
        if cuda.is_available():
            return  # 真 GPU 环境不打桩
    except Exception:  # noqa: BLE001
        pass
    from types import SimpleNamespace

    total_mem = 24 * 1024 ** 3
    props = SimpleNamespace(
        name="CUDA-EMU", total_memory=total_mem, major=8, minor=6,
        multi_processor_count=84, is_multi_gpu_board=False,
        L2_cache_size=4 * 1024 ** 2,
    )
    cuda.is_available = lambda: True
    cuda.device_count = lambda: 1
    cuda.current_device = lambda: 0
    cuda.set_device = lambda *a, **k: None
    cuda.get_device_name = lambda *a, **k: "CUDA-EMU"
    cuda.get_device_capability = lambda *a, **k: (8, 6)
    cuda.get_device_properties = lambda *a, **k: props
    cuda.mem_get_info = lambda *a, **k: (int(total_mem * 0.9), total_mem)
    cuda.memory_allocated = lambda *a, **k: 0
    cuda.memory_reserved = lambda *a, **k: 0
    cuda.max_memory_allocated = lambda *a, **k: 0
    cuda.max_memory_reserved = lambda *a, **k: 0
    cuda.reset_peak_memory_stats = lambda *a, **k: None
    cuda.empty_cache = lambda *a, **k: None
    cuda.synchronize = lambda *a, **k: None
    cuda.set_per_process_memory_fraction = lambda *a, **k: None
    cuda.memory_stats = lambda *a, **k: {}
    cuda.utilization = lambda *a, **k: 0
    print("[stub] torch.cuda patched for CPU-only introspection")


# ---------------------------------------------------------------- 主流程

def main():
    ap = argparse.ArgumentParser(description="TE_MAN node introspection")
    ap.add_argument("--comfyui", default=os.environ.get("COMFYUI_DIR"),
                    help="ComfyUI 根目录（含 folder_paths.py）")
    ap.add_argument("--package", default=os.environ.get("TE_MAN_PACKAGE", "TE_MAN"))
    ap.add_argument("--out", default=os.environ.get("TE_MAN_INTROSPECTION_OUT",
                                                    "te_man_introspection.json"))
    args, _ = ap.parse_known_args()

    # 关键：在导入任何 comfy 模块之前清空 argv —— comfy.cli_args 会在 import 时
    # 解析 sys.argv，遇到我们的 --out 等未知参数会直接 SystemExit。
    sys.argv = [os.path.basename(sys.argv[0])]

    # 关键：Windows runner 控制台默认 cp1252/charmap 编码，TE_MAN 的 logger 在
    # import 期间打印中文会直接 UnicodeEncodeError。强制 UTF-8。
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass

    # 输出路径先转绝对路径（后面会 os.chdir 到 ComfyUI 目录）
    if args.out:
        args.out = os.path.abspath(args.out)

    if not args.comfyui or not os.path.isdir(args.comfyui):
        print(f"[FATAL] ComfyUI 目录无效: {args.comfyui!r}", file=sys.stderr)
        return 2
    comfy_root = os.path.abspath(args.comfyui)
    custom_nodes = os.path.join(comfy_root, "custom_nodes")
    for p in (comfy_root, custom_nodes):
        if p not in sys.path:
            sys.path.insert(0, p)
    os.chdir(comfy_root)

    patch_torch_cuda_stub()

    result = {
        "env": {
            "python": sys.version,
            "platform": platform.platform(),
            "comfyui_dir": comfy_root,
        },
        "package": None,
        "node_class_mappings": {},
        "node_display_name_mappings": {},
        "web_directory": None,
        "nodes": {},
        "modules": {},
        "module_import_errors": {},
        "errors": [],
    }

    # 1. 导入 TE_MAN 包（__init__.py 会逐模块加载 pyd，单个失败不影响其余）
    try:
        pkg = importlib.import_module(args.package)
        result["package"] = pkg.__file__
        result["node_class_mappings"] = dict(getattr(pkg, "NODE_CLASS_MAPPINGS", {}))
        result["node_display_name_mappings"] = dict(
            getattr(pkg, "NODE_DISPLAY_NAME_MAPPINGS", {}))
        result["web_directory"] = getattr(pkg, "WEB_DIRECTORY", None)
    except Exception:  # noqa: BLE001
        result["errors"].append("package import failed:\n" + traceback.format_exc())

    # 2. 逐个节点类导出
    for name, cls in list(result["node_class_mappings"].items()):
        try:
            result["nodes"][name] = introspect_node_class(cls)
        except Exception:  # noqa: BLE001
            result["nodes"][name] = {"error": traceback.format_exc()}

    # 3. 已加载的包内模块逐个导出
    loaded = {m: sys.modules[m] for m in list(sys.modules)
              if m == args.package or m.startswith(args.package + ".")}

    # 4. 包目录下每个 pyd/py 若未成功加载，单独再试一次并记录错误
    pkg_dir = None
    if loaded:
        pkg_dir = os.path.dirname(list(loaded.values())[0].__file__ or "")
    else:
        pkg_dir = os.path.join(custom_nodes, args.package)
    if pkg_dir and os.path.isdir(pkg_dir):
        stems = [f[:-4] for f in os.listdir(pkg_dir) if f.endswith(".pyd")]
        stems += [f[:-3] for f in os.listdir(pkg_dir)
                  if f.endswith(".py") and f != "__init__.py"]
        for stem in sorted(set(stems)):
            full = f"{args.package}.{stem}"
            if full in loaded:
                continue
            try:
                importlib.import_module(full)
                loaded[full] = sys.modules[full]
            except Exception as e:  # noqa: BLE001
                result["module_import_errors"][full] = (
                    f"{type(e).__name__}: {e}\n{traceback.format_exc()}")

    for mname, mod in sorted(loaded.items()):
        try:
            result["modules"][mname] = introspect_module(mod)
        except Exception:  # noqa: BLE001
            result["modules"][mname] = {"error": traceback.format_exc()}

    # 5. 落盘 + 控制台摘要
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=repr)

    print("=" * 60)
    print(f"nodes registered      : {len(result['nodes'])}")
    for name in sorted(result["nodes"]):
        n = result["nodes"][name]
        cat = n.get("CATEGORY", "?") if isinstance(n, dict) else "?"
        print(f"  - {name:45s} [{cat}]")
    print(f"modules loaded        : {len(result['modules'])}")
    print(f"module import errors  : {len(result['module_import_errors'])}")
    for mname, err in result["module_import_errors"].items():
        print(f"  ! {mname}: {err.splitlines()[0]}")
    print(f"package-level errors  : {len(result['errors'])}")
    print(f"output                : {os.path.abspath(args.out)}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
