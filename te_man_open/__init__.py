# -*- coding: utf-8 -*-
"""te_man_open —— TE MAN 插件的纯 Python 重实现（依据 spec/ 逆向规格）。

结构：
- nodes/         节点实现（骨架由 tools/codegen_skeletons.py 生成，契约与原版一致）
- shared/        内部支撑库（config_manager / image_codec / task_runner / api_client / ...）
- web/           原版前端 JS 逐字复用（明文资产）

契约：tools/check_contract.py 保证本包对外暴露的节点注册面与原版真机数据一致。
"""

import importlib
import pkgutil

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
__version__ = "0.1.0"

for _m in pkgutil.iter_modules(__path__):
    if _m.name == "nodes":
        continue
    if _m.ispkg:
        continue
    try:
        _mod = importlib.import_module(f"{__name__}.{_m.name}")
    except Exception as _e:  # noqa: BLE001
        import logging

        logging.getLogger(__name__).error("加载节点模块失败 %s: %s", _m.name, _e)
        continue
    NODE_CLASS_MAPPINGS.update(getattr(_mod, "NODE_CLASS_MAPPINGS", {}))
    NODE_DISPLAY_NAME_MAPPINGS.update(getattr(_mod, "NODE_DISPLAY_NAME_MAPPINGS", {}))

# nodes/ 子包：遍历其中的节点模块并聚合
try:
    import pkgutil as _pkgutil

    _nodes_pkg = importlib.import_module(f"{__name__}.nodes")
    for _m in _pkgutil.iter_modules(_nodes_pkg.__path__):
        try:
            _mod = importlib.import_module(f"{_nodes_pkg.__name__}.{_m.name}")
        except Exception as _e:  # noqa: BLE001
            import logging

            logging.getLogger(__name__).error("加载节点模块失败 %s: %s", _m.name, _e)
            continue
        NODE_CLASS_MAPPINGS.update(getattr(_mod, "NODE_CLASS_MAPPINGS", {}))
        NODE_DISPLAY_NAME_MAPPINGS.update(getattr(_mod, "NODE_DISPLAY_NAME_MAPPINGS", {}))
except Exception as _e:  # noqa: BLE001
    import logging

    logging.getLogger(__name__).error("加载 nodes 子包失败: %s", _e)

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "__version__"]
WEB_DIRECTORY = "./web"
