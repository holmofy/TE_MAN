#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 spec/_introspection/te_man_introspection.json 生成 te_man_open/nodes/ 下的节点骨架。

生成内容（每个原始 pyd 模块一个文件）：
- 节点类：CATEGORY/FUNCTION/OUTPUT_NODE/RETURN_TYPES/RETURN_NAMES + INPUT_TYPES()
  —— 全部来自真机 introspection 数据，保证与原版逐字段一致
- 模块级 NODE_CLASS_MAPPINGS / NODE_DISPLAY_NAME_MAPPINGS

规则：INPUT_TYPES() 是契约，生成后禁止手改；实现工作只发生在 FUNCTION 对应方法里。
"""

import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLDEN = os.path.join(REPO, "spec", "_introspection", "te_man_introspection.json")
OUT_DIR = os.path.join(REPO, "te_man_open", "nodes")

# 注册名 -> 目标模块文件名（不含 .py）。默认按 class module 反解，覆盖特殊映射。
MODULE_OVERRIDES = {
    "TE_image_pro_grok_image": "Grok_Image_Generator",
    "TE_image_pro_gpt_image_2": "GPT_Image_2_Generator",
    "TE_image_pro_banana": "Gemini_Imagen_Generator",
    "TE_image_pro_special_async2": "Gemini_Imagen_Generator",
    "TE_image_pro_special_channel": "Gemini_Imagen_Generator",
    "TE_image_pro_grok_video": "Grok_Video_Generator",
    "TE_image_pro_sora2_video": "Sora_2_Video_Generator",
    "TE_image_pro_te_veo_video": "TE_VEO_Video",
    "TE_image_pro_happyh_video": "TE_HappyH_Video",
    "TE_image_pro_jimeng_video_2": "Jimeng_Video_Generator",
    "TE_image_pro_save_video": "Save_Video_With_Frame_Capture",
    "TE_image_pro_save_image_with_output": "Save_Image_With_Output",
    "TE_image_pro_text_tools": "TE_MAN_Text_Tools",
    "TE_image_pro_moss_layout": "TE_MAN_MOSS",
    "TE_image_pro_moss_box": "TE_MAN_MOSS",
    "TE_image_pro_compress": "TE_Image_Compress",
    "TE_image_pro_compress_test": "TE_Image_Compress_Test",
    "TE_image_pro_image_comparer": "TE_Image_Comparer",
    "TE_image_pro_video_comparer": "TE_Video_Comparer",
    "TE_Bernini_R_Generator": "TE_Bernini_R_Generator",
    "TE_Bernini_Prompt_Enhancer": "TE_Bernini_R_Generator",
    "TE_H3_Prompt_Enhancer": "TE_H3_Prompt_Enhancer",
    "TE_H3_Reference_Bridge": "TE_H3_Prompt_Enhancer",
    "TE_MAN_Batch_Prompt": "TE_Batch_Tools",
    "TE_MAN_Batch_Image": "TE_Batch_Tools",
    "TE_MAN_Batch_Enhanced_Settings": "TE_Batch_Tools",
    "TE_Qwen_Image_2_1_Prompt_Enhancer": "TE_Qwen_Image_2_1_Prompt_Enhancer",
    "TE_prompt_text": "TE_Prompt_Text",
    "TE_text_display": "TE_Text_Display",
    "TE_audio_save_load": "TE_Audio_Save_Load",
    "TE_3D_Director": "TE_3D_Director",
}


def tup(x):
    """JSON list -> Python tuple（ComfyUI 惯例），dict 保持，其余原样。"""
    if isinstance(x, list):
        return tuple(tup(i) for i in x)
    if isinstance(x, dict):
        return {k: tup(v) for k, v in x.items()}
    return x


def module_for(reg, node):
    if reg in MODULE_OVERRIDES:
        return MODULE_OVERRIDES[reg]
    mod = node.get("module") or ""
    for prefix in ("custom_nodes.TE_image.", "custom_nodes.TE_MAN."):
        if mod.startswith(prefix):
            return mod[len(prefix):]
    return "misc"


def gen_class(reg, node, display):
    cls = node["class"]
    lines = []
    lines.append(f"class {cls}:")
    lines.append(f'    """{display}')
    lines.append("")
    lines.append(f"    注册名: {reg}")
    lines.append(f"    规格:   spec/{module_for(reg, node)}.md（含动态 introspection 回填节）")
    lines.append("")
    lines.append("    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；")
    lines.append("    实现工作只发生在 FUNCTION 指向的方法中。")
    lines.append('    """')
    lines.append("")
    lines.append(f"    CATEGORY = {node['CATEGORY']!r}")
    lines.append(f"    FUNCTION = {node['FUNCTION']!r}")
    if node.get("OUTPUT_NODE") is not None:
        lines.append(f"    OUTPUT_NODE = {node['OUTPUT_NODE']!r}")
    if node.get("DESCRIPTION") is not None:
        lines.append(f"    DESCRIPTION = {node['DESCRIPTION']!r}")
    rt = node.get("RETURN_TYPES")
    rn = node.get("RETURN_NAMES")
    if rt is not None:
        lines.append(f"    RETURN_TYPES = {tuple(rt)!r}")
    if rn is not None:
        lines.append(f"    RETURN_NAMES = {tuple(rn)!r}")
    lines.append("")
    it = node.get("INPUT_TYPES", {})
    if it.get("ok"):
        body = tup(it["value"])
        lines.append("    @classmethod")
        lines.append("    def INPUT_TYPES(cls):")
        lines.append("        # --8<-- 契约开始（codegen 生成）--8<--")
        lines.append(f"        return {body!r}")
        lines.append("        # --8<-- 契约结束 --8<--")
    else:
        lines.append("    @classmethod")
        lines.append("    def INPUT_TYPES(cls):")
        lines.append(f"        raise NotImplementedError({it.get('error', 'gold INPUT_TYPES error')!r})")
    lines.append("")
    lines.append(f"    def {node['FUNCTION']}(self, **kwargs):")
    lines.append(f'        """TODO: 按 spec/{module_for(reg, node)}.md 实现。输入经 kwargs 传入。"""')
    lines.append("        raise NotImplementedError")
    return "\n".join(lines)


def main():
    with open(GOLDEN, encoding="utf-8") as f:
        gold = json.load(f)
    os.makedirs(OUT_DIR, exist_ok=True)

    files = {}  # module -> [chunks]
    for reg in sorted(gold["nodes"]):
        node = gold["nodes"][reg]
        display = gold["node_display_name_mappings"].get(reg, reg)
        mod = module_for(reg, node)
        chunk = gen_class(reg, node, display)
        mappings = (
            f"\n\nNODE_CLASS_MAPPINGS = {{{reg!r}: {node['class']}}}\n"
            f"NODE_DISPLAY_NAME_MAPPINGS = {{{reg!r}: {display!r}}}\n"
        )
        files.setdefault(mod, []).append(chunk + mappings)

    for mod, chunks in sorted(files.items()):
        path = os.path.join(OUT_DIR, mod + ".py")
        with open(path, "w", encoding="utf-8") as f:
            f.write("# -*- coding: utf-8 -*-\n")
            f.write(f'"""te_man_open · {mod}\n\n')
            f.write("本文件由 tools/codegen_skeletons.py 自动生成骨架。\n")
            f.write("INPUT_TYPES 为与原版逐字段一致的真机契约；请实现各 FUNCTION 方法。\n")
            f.write('"""\n\n')
            f.write("\n\n".join(chunks))
        print(f"  wrote {os.path.relpath(path, REPO)}")

    print(f"\nnodes: {len(gold['nodes'])}, files: {len(files)}")


if __name__ == "__main__":
    sys.exit(main())
