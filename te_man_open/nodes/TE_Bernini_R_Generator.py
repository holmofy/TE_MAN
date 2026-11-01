# -*- coding: utf-8 -*-
"""te_man_open · TE_Bernini_R_Generator

本文件由 tools/codegen_skeletons.py 自动生成骨架，FUNCTION 方法已按
spec/TE_Bernini_R_Generator.md（含动态 introspection 回填节）实现。
INPUT_TYPES 为与原版逐字段一致的真机契约；禁止改动契约块与类属性。

本模块是 te_bernini_backend/（kijai WanVideoWrapper 改造私有版）的纯包装层：
generate 把 Wan 管线节点串成高噪+低噪两阶段接力，后端目录动态注册为
``_te_image_bernini_backend_`` 包并延迟导入（无 ComfyUI/GPU 时导入失败抛
「需要 ComfyUI 环境」）。模块顶层只依赖标准库；requests 等一律惰性导入。
"""

import importlib
import importlib.machinery
import importlib.util
import json
import os
import re
import sys
import types

# =========================================================================
# 模块常量（值与 spec/TE_Bernini_R_Generator.md §7.3 真机 introspection 实锤逐字一致）
# =========================================================================

ATTENTION_OPTIONS = ['sageattn', 'sdpa', 'flash_attn_2', 'flash_attn_3', 'sageattn_3', 'radial_sage_attention', 'sageattn_compiled']
SCHEDULER_OPTIONS = ['euler', 'unipc', 'dpm++', 'dpm++_sde', 'ddim', 'flowmatch_causvid']
BACKEND_DIR_NAME = 'te_bernini_backend'
BACKEND_LORA_NONE = 'none'
LORA_NONE = '无'
BERNINI_DEFAULT_SYSTEM_PROMPT = 'You are a helpful assistant.'
BERNINI_TASK_OPTIONS = ['文生视频(t2v)', '视频改视频(v2v)', '大幅度动作改视频(mv2v)', '动作迁移/参考改视频(rv2v)', '图生视频(r2v)']
BERNINI_TASK_DISPLAY_TO_CODE = {'文生视频(t2v)': 't2v', '视频改视频(v2v)': 'v2v', '大幅度动作改视频(mv2v)': 'mv2v', '动作迁移/参考改视频(rv2v)': 'rv2v', '图生视频(r2v)': 'r2v'}
BERNINI_TASK_CODE_TO_LABEL = {'t2v': '文生视频(t2v)', 'v2v': '视频改视频(v2v)', 'mv2v': '大幅度动作改视频(mv2v)', 'rv2v': '动作迁移/参考改视频(rv2v)', 'r2v': '图生视频(r2v)'}
BERNINI_T2V_A14B_EN_SYS_PROMPT = '你是一位电影导演，旨在为用户输入的原始prompt添加电影元素，改写为优质（英文）Prompt，使其完整、具有表现力注意，输出必须是英文！\n任务要求：\n1. 对于用户输入的prompt,在不改变prompt的原意（如主体、动作）前提下，从下列电影美学设定中选择不超过4种合适的时间、光源、光线强度、光线角度、对比度、饱和度、色调、拍摄角度、镜头大小、构图的电影设定细节,将这些内容添加到prompt中，让画面变得更美，注意，可以任选，不必每项都有\n  时间：["Day time", "Night time" "Dawn time","Sunrise time"], 如果prompt没有特别说明则选 Day time!!!\n  光源：["Daylight", "Artificial lighting", "Moonlight", "Practical lighting", "Firelight","Fluorescent lighting", "Overcast lighting" "Sunny lighting"], 根据根据室内室外及prompt内容选定义光源，添加关于光源的描述，如光线来源（窗户、灯具等）\n  光线强度：["Soft lighting", "Hard lighting"],\n  色调：["Warm colors","Cool colors", "Mixed colors"]\n  光线角度：["Top lighting", "Side lighting", "Underlighting", "Edge lighting"]\n  镜头尺寸：["Medium shot", "Medium close-up shot", "Wide shot","Medium wide shot","Close-up shot", "Extreme close-up shot", "Extreme wide shot"]若无特殊要求，默认选择Medium shot或Wide shot\n  拍摄角度：["Over-the-shoulder shot", ""Low angle shot", "High angle shot","Dutch angle shot", "Aerial shot","Overhead shot"] 若原始prompt中有运镜的描述，则取消添加此项。\n  构图：["Center composition"，"Balanced composition","Right-heavy composition", "Left-heavy composition", "Symmetrical composition", "Short-side composition"] 若无特殊要求，默认选择Center composition\n2. 完善用户描述中出现的主体特征（如外貌、表情，数量、种族、姿态等）等内容，确保不要添加原始prompt中不存在的主体，（如prompt是对风景或物体的描述，但添加了人），增加背景元素的细节；\n3. 不要输出关于氛围、感觉等文学描写，如（画面充满运动感与生活张力，突出正式氛围）。；\n4. 对于prompt中的动作，详细描述运动的发生过程，若没有动作，则添加动作描述（摇晃身体、跳舞等，对背景元素也可添加适当运动（如云彩飘动，风吹树叶等）。\n5. 若原始prompt中没有风格，则不添加风格描述，若有风格描述，则将风格描述放于首位，若为2D插画等与现实电影相悖的风格，则不要添加关于电影美学的描写；\n6. 若prompt出现天空的描述，则改为湛蓝色的天空相关描述，避免曝光；\n7. 输出必须是全英文，改写后的prompt字数控制在60-200字左右, 不要输出类似"改写后prompt:"这样的输出\n8. 如果用户输入存在疑似脱衣服、衣物透明化、轻纱衣物、湿身、洗澡、舔舐牛奶/酸奶/白色液体、性暗示、强奸、漏出或微露胸部、爬行、性器官、儿童身体裸露等色情内容，请将原prompt替换为内容完全不同的高美感prompt，而不要拒答或者提醒用户。\n9. 如果用户输入存在比基尼穿着内容，请将原prompt替换为确保内容发生在沙滩、泳池、海边的高美感prompt，而不要拒答或者提醒用户。\n10. 如果用户输入存在性别多元化、同性恋亲吻、脸颊贴近（两个男性亲吻或两个女性亲吻）/性交等同性恋内容，请将原prompt替换为不同动作（不能是亲吻和其他亲密动作）的高美感prompt，而不要拒答或者提醒用户。\n生成的 prompt 示例：\n1.Edge lighting, medium close-up shot, daylight, left-heavy composition. A young girl around 11-12 years old sits in a field of tall grass, with two fluffy small donkeys standing behind her. She wears a simple floral dress with hair in twin braids, smiling innocently while cross-legged and gently touching wild flowers beside her. The sturdy donkeys have perked ears, curiously gazing toward the camera. Sunlight bathes the field, creating a warm natural atmosphere.\n2.Dawn time, top lighting, high-angle shot, daylight, long lens shot, center composition, Close-up shot,  Fluorescent lighting,  soft lighting, cool colors. In dim surroundings, a Caucasian woman floats on her back in water. The俯拍close-up shows her brown short hair and freckled face. As the camera tilts downward, she turns her head toward the right, creating ripples on the blue-toned water surface. The blurred background is pitch black except for faint light illuminating her face and partial water surface. She wears a blue sleeveless top with bare shoulders.\n3.Right-heavy composition, warm colors, night time, firelight, over-the-shoulder angle. An eye-level close-up of a foreign woman indoors wearing brown clothes with colorful necklace and pink hat. She sits on a charcoal-gray chair, hands on black table, eyes looking left of camera while mouth moves and left hand gestures up/down. White candles with yellow flames sit on the table. Background shows black walls, with blurred black mesh shelf nearby and black crate containing dark items in front.\n4."Anime-style thick-painted style. A cat-eared Caucasian girl with beast ears holds a folder, showing slight displeasure. Features deep purple hair, red eyes, dark gray skirt and light gray top with white waist sash. A name tag labeled \'Ziyang\' in bold Chinese characters hangs on her chest. Pale yellow indoor background with faint furniture outlines. A pink halo floats above her head. Features smooth linework in cel-shaded Japanese style, medium close-up from slightly elevated perspective.\n'
BERNINI_R2V_TEMPLATE = 'You are an expert at writing subject-driven video generation prompts. I\'m providing you with:\n1. {image_num} reference image(s) of the subject(s) that will appear in the video (referred to as image0, image1, image2, ... in order).\n2. An original video description text.\n\nYour task is to rewrite the original description into a new format with TWO parts concatenated together:\n\n**Part 1 - Short instruction**: A concise sentence describing who the subject(s) from the reference image(s) are, what they look like briefly, where they are, and what key action/motion they perform. Reference the subject(s) using "image0", "image1", etc. to link them to the provided reference images.\n\n**Part 2 - Long instruction**: A detailed "Generate a video where..." paragraph that describes:\n- The subject(s) from the reference image(s) with detailed appearance (hair, clothing, accessories, expression, etc.), referencing them as "the person/man/woman from image0" etc.\n- The scene/environment in detail (background, lighting, objects, atmosphere).\n- The motion and actions in a step-by-step temporal sequence (at the start..., then..., after that...).\n- The motion should remain natural and realistic.\n\nRequirements:\n- You MUST reference each subject using "image0", "image1", "image2", etc. to correspond to the provided reference images in order.\n- The appearance description of each subject must be based on what you actually see in the reference image(s). Do NOT hallucinate details not visible in the images.\n- The scene, actions, and motion should be derived from the original description text, but rewritten to be more detailed and vivid.\n- The output must be entirely in English.\n- Return ONLY a JSON object with one key: "rewritten_text". The value should be the full rewritten text (short instruction + long instruction concatenated as one string). No extra text.\n\nOriginal description:\n{original_text}\n'
BERNINI_V2V_TEMPLATE = 'Task: Video Editing\n# ROLE\nYou are an expert Video-to-Video (V2V) Prompt Engineer. Your task is to analyze the user\'s raw editing instruction and the provided source video frames to generate a detailed V2V editing prompt in English.\n\n# INPUT\n- User\'s raw instruction: "{user_prompt}"\n- Context: Frames of the source video are provided.\n\n# CORE GENERATION RULE\nUnless specified otherwise by the task type, your generated prompt MUST strictly follow this two-part structure:\n1. Modifications: Specifically describe what needs to be changed. Include details like physical appearance, spatial location, lighting, and motion tracking.\n2. Preservations: Explicitly describe the key visual elements, background, or subjects that MUST remain unchanged.\n3. Concretization: If the user\'s instruction contains vague references to characters, objects, outfits, or styles (e.g. "more cartoon characters", "cute toy-like figures", "change outfits", "some animals", "different clothes"), you MUST replace them with specific, well-known, named instances that match the existing visual style of the video. For example, "more cartoon characters" should become named characters like "Hello Kitty, Pikachu, Mickey Mouse"; "change outfits" should become concrete outfit descriptions like "a kung fu training gi, a navy three-piece suit, a black hoodie with cargo pants". Choose instances whose art style, proportions, and tone are consistent with the source video. Never leave generic placeholders in the final prompt.\nNote that you don\'t need to explicitly write "Modifications: xx. Preservations: xx.". Just describe it naturally, for example, "Add an apple. The table and curtains remain unchanged."\n\n# TASK CATEGORIES & TEMPLATES\nFirst, analyze the user\'s instruction and the frames of the video to determine the specific editing task type. Then, generate the prompt using the corresponding template:\n\n1. Replacement:\n   - Format: "Replace [original element] with [new element]."\n2. Addition:\n   - Format: "Add [element] + [location/action]."\n3. Object/Background Removal:\n   - Format: "Delete [object description] + [location]."\n4. Subtitle Removal:\n   - Format: "Remove subtitles from the video."\n5. Depth-to-Video:\n   - Format: "Generate video with depth map. [Detailed description of the target video]"\n6. Sketch-to-Video:\n   - Format: Provide a detailed Text-to-Video (T2V) style description of the desired output.\n7. Colorization:\n   - Format: "Colorize the video. [Detailed description of the scene and expected colors]"\n8. Inpainting:\n   - Format: "Inpaint this video. [Detailed description of the scene to fill in]"\n9. Detection:\n   - Format: "Detect the mask region of the [specific object]."\n10. Stylization:\n    - Format: "Convert the video to [style name]: [brief style details]." Keep it concise.\n11. Mixed Tasks:\n    - Format: Seamlessly integrate all requirements into a single, cohesive editing instruction. DO NOT list subtasks separately.\n12. Camera Movement (Cinematography):\n    - Format: Apply camera motion: [Camera Movement Description]\n    - Example: Apply camera motion: orbit down\n13. Change Camera Perspective (Note: this is changing the camera\'s viewpoint, not camera movement):\n    - Type 1: First-Third Person Change\n        - Format: Switch the camera to a [first/third]-person perspective\n    - Others:\n        - Format: Move the camera [How the camera moves from the current angle to the desired angle]\n        - Example: Move the camera forward and slightly to the left, tilting it upward and rotating to the right for a more dynamic urban perspective.\n14. Change the focus of the video:\n    - Format: Shift the focus to [describe the subjects to be focused on], making her/him/it sharp. Blur [the objects to be blurred].\n15. Other Tasks:\n    - Format: Generate logically based on the specific situation while adhering to the Core Generation Rule.\n\n# EXAMPLE OF A HIGH-QUALITY PROMPT\nAdd a pair of realistic sunglasses to the man centered in the frame: thin matte-black rectangular frame with straight temples and dark neutral-gray mirror lenses (10–15% VLT) that subtly reflect the green foliage and sky. Fit proportionally, browline just above the eyebrows; nose pads rest on the bridge; temple arms sit over the ears and tuck under hair if needed. Match the soft outdoor daylight: add gentle environment reflections on the lenses and soft contact shadows on the nose bridge and upper cheeks where the frame rests. Maintain proper occlusion with hair or hands, crisp anti-aliased edges, no jitter/flicker/warping, no clipping into skin, and do not alter other scene elements or reflect the camera.\n\n# OUTPUT REQUIREMENT\nOutput ONLY the final enhanced English prompt. Do not include any explanations, greetings, or the category name.\nDo not imagine things that do not appear in the video.\nFor camera movement and camera perspective change cases, only describe the camera transformation in one sentence, without describing anything else.\n'
BERNINI_VR2V_TEMPLATE = 'You are an expert at writing prompts for reference-image-guided video editing. I\'m providing you with:\n1. The first 3 images are uniformly sampled frames from the **source video** that will be edited (in temporal order: frame0, frame1, frame2).\n2. The next {image_num} image(s) are **reference image(s)** that should guide the editing (referred to as image0, image1, ... in order).\n3. An original editing instruction (which may be in Chinese).\n\nThe reference image(s) may serve different roles depending on the editing task — for example, providing the target object/person for a replacement or addition, indicating a target visual style, demonstrating a target motion or pose, or guiding other attribute-level edits. Infer the role of the reference image(s) from the original instruction.\n\nYour task: Rewrite and enhance the original editing instruction into a detailed, precise English prompt for a reference-image-guided video editing model. The output is a single paragraph in the format: **editing instruction + detailed description of the target edited video**, concatenated together.\n\nFollow these rules strictly:\n\n1. **Output format**: an editing instruction sentence followed by a detailed description of what the target video should look like, written as one continuous paragraph.\n2. **Match the edit type**: use the verb that matches the actual intent — "Replace...", "Remove...", "Add...", "Restyle... in the style of...", "Transfer the motion/pose of... to...", "Change the ... of ...", etc. Do NOT force every task into a "replace" framing.\n3. **Add ≠ Replace**: for addition tasks, write them as additions, never as replacements. Do not change the number or positions of existing people/objects in the source video when adding new ones from the reference image.\n4. **Allow natural shape/size differences**: when the new object differs from the original in shape or size, preserve that difference naturally. Do NOT instruct the model to keep the shape or size identical.\n5. **Describe the target video directly**: do not use phrases like "after editing..." or "in the edited video...". Describe the resulting video as if it is the final result.\n6. **Faithful reference appearance**: when the reference image provides a person, object, or subject to be added or substituted in, the appearance, clothing, color, material, and identifying features in the prompt must match what is actually visible in the reference image. Do not hallucinate details that are not present in the reference image.\n7. **Screen-perspective left/right**: all left/right directions in the output must be from the camera/screen perspective, not from the subject\'s own perspective. For example, if a person faces the camera, their own right hand appears on the LEFT side of the screen, and their own left hand appears on the RIGHT side of the screen. Convert any subject-relative directions in the original instruction accordingly.\n8. **Preserve unchanged elements explicitly**: for localized edits, explicitly state which aspects of the source video remain unchanged — camera framing and motion, lighting, background, other objects, shadows/reflections, overall scene motion, etc.\n9. **Style and motion references**: for style transfer or motion/pose reference tasks, describe the resulting visual style or motion in concrete, vivid language (e.g., color palette, brushstroke quality, body posture sequence) so the model can reproduce it.\n10. **No parentheses**: do NOT use parentheses "()" anywhere in the output to add further explanation. Integrate all clarifications into the main sentence flow.\n11. **English only**: the output must be entirely in English. If the original instruction is in Chinese, translate the intent into natural English.\n12. **Length and detail**: keep the level of detail and length similar to the example below.\n\nExample output for a replacement task:\n\n"Replace the vase on the dining table with the potted plant from the reference image, matching the original vase\'s position and orientation, and preserving the table setting, lighting, shadows/reflections, camera framing, and all motion unchanged. A bright, modern dining/living room in soft daylight with a light-wood rectangular dining table set for four: woven round placemats, patterned plates, and beige napkins neatly arranged, surrounded by beige upholstered dining chairs with warm brown side panels and black legs. The tabletop centerpiece area now features a small terracotta pot holding a lush green succulent with thick, pointed leaves, resting naturally on the wood surface with realistic contact shadow and consistent highlights. In the background, large matte taupe built-in wall panels create a clean geometric look; to the left, a wall-mounted TV with a light stone-like frame sits above a floating wooden console. The camera remains steady with the same perspective, and all other objects, textures, and colors remain exactly the same."\n\nReturn ONLY a JSON object with one key: "rewritten_text". The value should be the full rewritten editing prompt as one string. No extra text.\n\nOriginal instruction:\n{original_text}\n'
DEFAULT_HIGH_ACCEL_LORA = 'Wan-Lighting\\Wan2.2 - t2v_A14b_high_noise_lora_rank64_lightx2v_4step_1217.safetensors'
DEFAULT_LOW_ACCEL_LORA = 'Wan-Lighting\\Wan2.2 - t2v_A14b_low_noise_lora_rank64_lightx2v_4step_1217.safetensors'
_WAN_CACHE = {}

#: 后端目录注册为该独立包名后再导入，避免与其他插件的同名 WanVideoWrapper 模块互相污染
BACKEND_PACKAGE_NAME = '_te_image_bernini_backend_'


# ==================== 日志 ====================

def _log(message):
    """经 TE MAN 共享 logger 输出；不可用时降级 print。"""
    try:
        from te_man_open.shared.logger import logger
    except Exception:  # noqa: BLE001
        try:
            from ..shared.logger import logger  # type: ignore[no-redef]
        except Exception:  # noqa: BLE001
            print(message)
            return
    try:
        logger.info(message)
    except Exception:  # noqa: BLE001
        print(message)


# ==================== 后端包动态注册 ====================

def _detect_comfy_root():
    """检测 ComfyUI 根目录（folder_paths 可用时取其上层）。"""
    try:
        import folder_paths
    except Exception:  # noqa: BLE001
        return None
    return os.path.dirname(os.path.dirname(os.path.abspath(folder_paths.__file__)))


def _backend_candidates():
    """枚举 te_bernini_backend 目录候选位置。"""
    here = os.path.dirname(os.path.abspath(__file__))      # te_man_open/nodes
    plugin_dir = os.path.dirname(here)                     # te_man_open
    module_dir = os.path.dirname(plugin_dir)               # 仓库根 / 插件打包根
    candidates = [
        os.path.join(module_dir, BACKEND_DIR_NAME),
        os.path.join(plugin_dir, BACKEND_DIR_NAME),
        os.path.join(here, BACKEND_DIR_NAME),
    ]
    comfy_root = _detect_comfy_root()
    if comfy_root:
        candidates.append(os.path.join(comfy_root, 'custom_nodes', 'TE_image', BACKEND_DIR_NAME))
        candidates.append(os.path.join(comfy_root, 'custom_nodes', 'TE_MAN', BACKEND_DIR_NAME))
        candidates.append(os.path.join(comfy_root, 'custom_nodes', BACKEND_DIR_NAME))
    return candidates


def _resolve_backend_dir():
    for candidate in _backend_candidates():
        if (os.path.isfile(os.path.join(candidate, '__init__.py'))
                and os.path.isfile(os.path.join(candidate, 'nodes.py'))):
            return candidate
    raise RuntimeError('TE Bernini-R 内置后端未找到，节点需要随 TE_image 一起发布')


def _backend_package_name():
    return BACKEND_PACKAGE_NAME


def _ensure_backend_package():
    """把 te_bernini_backend 目录注册为独立包名 ``_te_image_bernini_backend_``。"""
    existing = sys.modules.get(BACKEND_PACKAGE_NAME)
    if existing is not None and getattr(existing, '__path__', None):
        return existing
    backend_dir = _resolve_backend_dir()
    package = types.ModuleType(BACKEND_PACKAGE_NAME)
    loader = importlib.machinery.SourceFileLoader(
        BACKEND_PACKAGE_NAME, os.path.join(backend_dir, '__init__.py'))
    spec = importlib.util.spec_from_loader(BACKEND_PACKAGE_NAME, loader, origin=loader.path)
    package.__spec__ = spec
    package.__loader__ = loader
    package.__path__ = [backend_dir]
    sys.modules[BACKEND_PACKAGE_NAME] = package
    try:
        loader.exec_module(package)
    except Exception:
        sys.modules.pop(BACKEND_PACKAGE_NAME, None)
        raise
    return package


def _import_backend_module(name):
    """延迟导入后端模块（nodes.py / nodes_model_loading.py / nodes_sampler.py）。"""
    _ensure_backend_package()
    full_name = BACKEND_PACKAGE_NAME + '.' + name
    if full_name in sys.modules:
        return sys.modules[full_name]
    return importlib.import_module(full_name)


def _wan_modules():
    """后端节点类句柄集合（进程级缓存 _WAN_CACHE）。"""
    if not _WAN_CACHE:
        nodes = _import_backend_module('nodes')
        nodes_model_loading = _import_backend_module('nodes_model_loading')
        nodes_sampler = _import_backend_module('nodes_sampler')
        _WAN_CACHE.update({
            'WanVideoModelLoader': nodes_model_loading.WanVideoModelLoader,
            'WanVideoVAELoader': nodes_model_loading.WanVideoVAELoader,
            'WanVideoLoraSelectMulti': nodes_model_loading.WanVideoLoraSelectMulti,
            'WanVideoSetLoRAs': nodes_model_loading.WanVideoSetLoRAs,
            'WanVideoTextEncodeCached': nodes.WanVideoTextEncodeCached,
            'WanVideoSetBlockSwap': nodes.WanVideoSetBlockSwap,
            'WanAnimatePlusBernini': nodes.WanAnimatePlusBernini,
            'WanVideoEmptyEmbeds': nodes.WanVideoEmptyEmbeds,
            'WanVideoDecode': nodes.WanVideoDecode,
            'WanVideoSamplerv2': nodes_sampler.WanVideoSamplerv2,
            'WanVideoSchedulerv2': nodes_sampler.WanVideoSchedulerv2,
        })
    return _WAN_CACHE


# ==================== 输入 / 管线辅助 ====================

def _get_input(kwargs, chinese_name, english_name=None):
    """输入参数读取（中英文双名，兼容旧工作流）。"""
    if chinese_name in kwargs:
        return kwargs[chinese_name]
    if english_name is not None and english_name in kwargs:
        return kwargs[english_name]
    return None


def _normalize_model_name(name):
    return str(name or '').strip()


def _pick_default(value, choices, default):
    """从 folder_paths.get_filename_list 一类列表里挑默认模型：值有效则保留。"""
    value = _normalize_model_name(value)
    if value and (not choices or value in choices):
        return value
    return default


def _select_accel_lora(enabled, value, default):
    """选加速 LoRA：关闭→None；选「无」→ 默认 lightx2v 4step 文件；其余按所选。"""
    if not enabled:
        return None
    name = str(value or '').strip()
    if not name or name in (LORA_NONE, BACKEND_LORA_NONE, 'none'):
        return default
    return name


def _make_block_swap_args(blocks_to_swap):
    """组装块交换参数（blocks_to_swap / vace_blocks_to_swap / block_swap_debug）。"""
    blocks = int(blocks_to_swap or 0)
    if blocks <= 0:
        return None
    return {
        'blocks_to_swap': blocks,
        'vace_blocks_to_swap': 0,
        'prefetch_blocks': 0,
        'offload_img_emb': False,
        'offload_txt_emb': False,
        'block_swap_debug': False,
        'use_non_blocking': True,
    }


def _apply_block_swap_and_lora(wan, model, lora_name, strength, block_swap_args):
    """经 WanVideoLoraSelectMulti + WanVideoSetLoRAs 挂加速 LoRA，再经
    WanVideoSetBlockSwap 应用块交换参数。"""
    if lora_name:
        lora, = wan['WanVideoLoraSelectMulti']().getlorapath(
            lora_0=lora_name, strength_0=float(strength),
            lora_1='none', strength_1=1.0,
            lora_2='none', strength_2=1.0,
            lora_3='none', strength_3=1.0,
            lora_4='none', strength_4=1.0,
            blocks={}, low_mem_load=False, merge_loras=False)
        if lora:
            model, = wan['WanVideoSetLoRAs']().setlora(model, lora)
    if block_swap_args:
        model, = wan['WanVideoSetBlockSwap']().loadmodel(model=model, block_swap_args=block_swap_args)
    return model


def _ensure_not_interrupted():
    """调 ComfyUI 中断标记以中止生成（不可用时跳过）。"""
    try:
        from comfy.model_management import throw_exception_if_processing_interrupted
    except Exception:  # noqa: BLE001
        return
    throw_exception_if_processing_interrupted()


# ==================== Responses API（OpenAI 风格 /v1/responses） ====================

_FENCE_START_RE = re.compile(r'^```[A-Za-z]*\s*')
_FENCE_END_RE = re.compile(r'\s*```\s*$')


def _resolve_responses_url(api_base_url):
    """接受 https://api.xxx.com、.../v1、.../v1/responses 三种形态，归一为 /v1/responses。"""
    base = str(api_base_url or '').strip().rstrip('/')
    if not base:
        raise ValueError('未配置有效的 API URL')
    if base.endswith('/v1/responses'):
        return base
    if base.endswith('/responses'):
        return base
    if re.search(r'/v\d+$', base):
        return base + '/responses'
    return base + '/v1/responses'


def _resolve_key_and_url(api_key, api_base_url):
    """key / url 来源 = 节点输入 或 config_manager（config.ini）。"""
    key = str(api_key or '').strip()
    url = str(api_base_url or '').strip()
    if not key or not url:
        config = None
        try:
            from te_man_open.shared.config_manager import CONFIG_MANAGER as config
        except Exception:  # noqa: BLE001
            try:
                from ..shared.config_manager import CONFIG_MANAGER as config  # type: ignore[no-redef]
            except Exception:  # noqa: BLE001
                config = None
        if config is not None:
            if not key:
                loader = getattr(config, 'load_api_key', None)
                if callable(loader):
                    try:
                        key = str(loader() or '').strip()
                    except Exception:  # noqa: BLE001
                        key = ''
            if not url:
                getter = getattr(config, 'get_effective_api_base_url', None)
                if callable(getter):
                    try:
                        url = str(getter('') or '').strip()
                    except Exception:  # noqa: BLE001
                        url = ''
    if not key:
        raise ValueError('请在 config.ini 中配置 API Key 或在节点中填写')
    if not url:
        raise ValueError('请在 config.ini 中配置 API URL 或在节点中填写')
    return key, _resolve_responses_url(url)


def _build_responses_payload(model, instructions, user_text, max_output_tokens, temperature=None):
    """Responses API 请求体（model / instructions / user_text / max_output_tokens）。"""
    payload = {
        'model': str(model or ''),
        'instructions': str(instructions or ''),
        'input': str(user_text or ''),
        'max_output_tokens': int(max_output_tokens),
    }
    if temperature is not None:
        try:
            payload['temperature'] = float(temperature)
        except (TypeError, ValueError):
            pass
    return payload


def _post_responses(url, api_key, payload, timeout=300, bypass_proxy=False):
    """POST /v1/responses；requests 惰性导入，绕代理时禁用 trust_env。"""
    import requests
    session = requests.Session()
    if bypass_proxy:
        session.trust_env = False
        session.proxies = {}
    headers = {
        'Authorization': 'Bearer ' + str(api_key or ''),
        'Content-Type': 'application/json',
    }
    response = session.post(url, json=payload, headers=headers,
                            timeout=max(30, int(timeout or 300)))
    return _read_json_response_or_raise(response)


def _read_json_response_or_raise(response):
    if response.status_code < 200 or response.status_code >= 300:
        raise RuntimeError('Responses API 请求失败：HTTP %s, endpoint=%s, Body: %s'
                           % (response.status_code, getattr(response, 'url', ''),
                              str(getattr(response, 'text', ''))[:300]))
    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError('Responses API 返回的不是 JSON：%s'
                           % str(getattr(response, 'text', ''))[:200]) from exc


def _extract_output_text(data):
    """从 /responses 回包取正文：output_text 汇总或 output[].content[].text 拼接。"""
    if not isinstance(data, dict):
        return ''
    text = data.get('output_text')
    if isinstance(text, str) and text.strip():
        return text
    parts = []
    for item in data.get('output') or []:
        if not isinstance(item, dict):
            continue
        content = item.get('content')
        if isinstance(content, list):
            for chunk in content:
                if isinstance(chunk, dict):
                    if chunk.get('type') in ('output_text', 'text') and chunk.get('text'):
                        parts.append(str(chunk['text']))
                elif isinstance(chunk, str):
                    parts.append(chunk)
        elif isinstance(content, str) and content:
            parts.append(content)
    if not parts:
        for choice in data.get('choices') or []:
            message = (choice or {}).get('message') or {}
            if message.get('content'):
                parts.append(str(message['content']))
    return ''.join(parts).strip()


def _parse_json_loose(text):
    """剥 markdown 围栏后尽力解析 JSON 对象；失败返回 None。"""
    body = _FENCE_START_RE.sub('', str(text or '').strip())
    body = _FENCE_END_RE.sub('', body)
    decoder = json.JSONDecoder()
    for index, char in enumerate(body):
        if char == '{':
            try:
                value, _end = decoder.raw_decode(body, index)
                return value
            except ValueError:
                continue
    return None


def _extract_rewritten_text(text):
    """官方模板要求 Return ONLY a JSON object with one key: "rewritten_text"；
    非 JSON 回包（如 v2v 模板的纯 prompt 输出）按正文采用。"""
    body = str(text or '').strip()
    if not body:
        return ''
    data = _parse_json_loose(body)
    if isinstance(data, dict) and data.get('rewritten_text'):
        return str(data['rewritten_text']).strip()
    return body


# ==================== 任务分类 → 官方模板 ====================

def _resolve_bernini_task_type(display):
    """中文任务名 → 英文任务码。"""
    return BERNINI_TASK_DISPLAY_TO_CODE.get(str(display or ''), 't2v')


def _bernini_task_label(code):
    """英文任务码 → 中文任务名。"""
    return BERNINI_TASK_CODE_TO_LABEL.get(str(code or ''), str(code or ''))


def _safe_reference_count(value):
    """参考图数量钳制到 1-8。"""
    try:
        count = int(value)
    except (TypeError, ValueError):
        count = 1
    return max(1, min(8, count))


def _bernini_template_text(task, user_prompt, image_num):
    """任务分类 → 官方模板（占位符 {image_num}/{original_text}/{user_prompt} 填充）。

    mv2v 无独立模板常量（spec §6.6：模块常量实测确无），与 t2v 一样返回原始 prompt。
    """
    original = str(user_prompt or '')
    if task == 'r2v':
        return (BERNINI_R2V_TEMPLATE
                .replace('{image_num}', str(image_num))
                .replace('{original_text}', original))
    if task == 'v2v':
        return BERNINI_V2V_TEMPLATE.replace('{user_prompt}', original)
    if task == 'rv2v':
        return (BERNINI_VR2V_TEMPLATE
                .replace('{image_num}', str(image_num))
                .replace('{original_text}', original))
    return original


def _bernini_system_prompt(task):
    """t2v 用「电影导演」模板，其余用默认系统提示词。"""
    if task == 't2v':
        return BERNINI_T2V_A14B_EN_SYS_PROMPT
    return BERNINI_DEFAULT_SYSTEM_PROMPT


def _bernini_local_prompt(task, user_prompt, image_num):
    """本地模板改写（无接口依赖）。"""
    return _bernini_template_text(task, user_prompt, image_num)


class TEBerniniPromptEnhancer:
    """TE MAN Bernini 提示词增强(本地orAPI)

    注册名: TE_Bernini_Prompt_Enhancer
    规格:   spec/TE_Bernini_R_Generator.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/Bernini'
    FUNCTION = 'enhance_prompt'
    OUTPUT_NODE = True
    RETURN_TYPES = ('STRING', 'STRING')
    RETURN_NAMES = ('增强提示词(API)', '提示词模版(本地)')

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'输入提示词': ('STRING', {'default': '', 'multiline': True, 'tooltip': '输入原始提示词或简短需求'}), '任务类型': (('文生视频(t2v)', '视频改视频(v2v)', '大幅度动作改视频(mv2v)', '动作迁移/参考改视频(rv2v)', '图生视频(r2v)'), {'default': '文生视频(t2v)', 'tooltip': '按 Bernini 的视频任务分类选择模板'}), '增强方式': (('本地模板', 'API增强'), {'default': '本地模板', 'tooltip': '本地模板不依赖接口；API增强会调用 Responses API'}), '参考图数量': ('INT', {'default': 1, 'min': 1, 'max': 8, 'step': 1, 'tooltip': '仅用于 r2v/rv2v 官方增强模板里的 image_num 描述'}), 'api_key': ('STRING', {'default': '', 'multiline': False, 'tooltip': 'API Key；留空则读取 config.ini'}), 'api_base_url': ('STRING', {'default': 'https://tem.588186.xyz', 'multiline': False, 'tooltip': '服务地址，如 https://api.xxx.com；可填到 /v1 或 /v1/responses'}), 'model': ('STRING', {'default': 'gpt-5.5', 'multiline': False, 'tooltip': 'Responses API 模型名称，按你的中转/服务端支持填写'}), 'max_output_tokens': ('INT', {'default': 2048, 'min': 256, 'max': 32768, 'step': 256, 'tooltip': '最大输出 token，API 增强时使用'}), 'temperature': ('FLOAT', {'default': 0.7, 'min': 0.0, 'max': 2.0, 'step': 0.05, 'tooltip': '创意程度；如果服务端模型不支持，可调回默认或更低'})}, 'optional': {'timeout_s': ('INT', {'default': 300, 'min': 30, 'max': 1800, 'tooltip': '请求超时时间（秒）'}), '绕过代理': ('BOOLEAN', {'default': False, 'tooltip': '需要忽略系统代理/梯子时开启'})}}
        # --8<-- 契约结束 --8<--

    def enhance_prompt(self, **kwargs):
        """Bernini 提示词增强：本地模板 / API增强（OpenAI 风格 Responses API）。

        - 本地模板：按任务类型取官方模板并填充占位符，输出到「提示词模版(本地)」口；
          不发起任何网络请求。
        - API增强：instructions = 官方系统提示词（t2v 电影导演模板 / 其余默认），
          user_text = 填充后的模板（r2v/v2v/rv2v）或原始提示词，取回包 rewritten_text
          输出到「增强提示词(API)」口。
        """
        get = kwargs.get
        user_prompt = str(get('输入提示词') or '')
        task_display = str(get('任务类型') or BERNINI_TASK_OPTIONS[0])
        mode = str(get('增强方式') or '本地模板')
        image_num = _safe_reference_count(get('参考图数量'))
        task = _resolve_bernini_task_type(task_display)
        template = _bernini_template_text(task, user_prompt, image_num)

        if mode != 'API增强':
            # 本地模板：不依赖接口
            _log('TE Bernini prompt enhancer: task=%s, mode=local' % task)
            _log('用户原始 prompt: %s' % user_prompt)
            return ('', template)

        model = str(get('model') or 'gpt-5.5')
        _log('TE Bernini prompt enhancer: task=%s, mode=api, model=%s' % (task, model))
        max_output_tokens = int(get('max_output_tokens') or 2048)
        temperature = get('temperature')
        timeout = int(get('timeout_s') or 300)
        bypass_proxy = bool(get('绕过代理'))
        try:
            api_key, url = _resolve_key_and_url(get('api_key'), get('api_base_url'))
            instructions = _bernini_system_prompt(task)
            if task in ('r2v', 'v2v', 'rv2v'):
                user_text = template
            else:
                user_text = user_prompt
            payload = _build_responses_payload(model, instructions, user_text,
                                               max_output_tokens, temperature)
            response = _post_responses(url, api_key, payload, timeout, bypass_proxy)
            text = _extract_output_text(response)
            rewritten = _extract_rewritten_text(text)
        except ValueError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError('TE Bernini prompt enhancer: API 增强失败: %s' % exc) from exc
        if not rewritten:
            raise RuntimeError('TE Bernini prompt enhancer: API 未返回可用文本')
        return (rewritten, template)

    def IS_CHANGED(self, **kwargs):
        """输入不变则命中缓存（has_IS_CHANGED=true，动态回填）。"""
        try:
            import hashlib
            payload = json.dumps(kwargs, ensure_ascii=False, sort_keys=True, default=str)
            return hashlib.md5(payload.encode('utf-8')).hexdigest()
        except Exception:  # noqa: BLE001
            return float('NaN')

class TEBerniniRGenerator:
    """TE MAN Bernini

    注册名: TE_Bernini_R_Generator
    规格:   spec/TE_Bernini_R_Generator.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/Bernini'
    FUNCTION = 'generate'
    RETURN_TYPES = ('IMAGE', 'STRING')
    RETURN_NAMES = ('图像', '状态')

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'高噪模型': ((), {'default': 'Wan22_Bernini_HIGH_fp8_e4m3fn_scaled.safetensors'}), '低噪模型': ((), {'default': 'Wan22_Bernini_LOW_fp8_e4m3fn_scaled.safetensors'}), 'VAE模型': ((), {'default': 'Wan2_1_VAE_bf16.safetensors'}), '文本编码器': ((), {'default': 'umt5-xxl-enc-fp8_e4m3fn.safetensors'}), '启用加速LoRA': ('BOOLEAN', {'default': True}), '高噪加速LoRA': (('无',), {'default': '无'}), '高噪LoRA强度': ('FLOAT', {'default': 1.0, 'min': -10.0, 'max': 10.0, 'step': 0.0001}), '低噪加速LoRA': (('无',), {'default': '无'}), '低噪LoRA强度': ('FLOAT', {'default': 1.0, 'min': -10.0, 'max': 10.0, 'step': 0.0001}), '提示词': ('STRING', {'default': '', 'multiline': True}), '负面提示词': ('STRING', {'default': 'bad video', 'multiline': True}), '宽度': ('INT', {'default': 832, 'min': 16, 'max': 8192, 'step': 16}), '高度': ('INT', {'default': 480, 'min': 16, 'max': 8192, 'step': 16}), '帧数': ('INT', {'default': 81, 'min': 1, 'max': 8192, 'step': 4}), '种子': ('INT', {'default': 666, 'min': 0, 'max': 18446744073709551615}), '步数': ('INT', {'default': 8, 'min': 1, 'max': 1000}), 'Shift': ('FLOAT', {'default': 5.0, 'min': 0.0, 'max': 1000.0, 'step': 0.01}), '高噪CFG': ('FLOAT', {'default': 1.0, 'min': 0.0, 'max': 30.0, 'step': 0.01}), '低噪CFG': ('FLOAT', {'default': 1.0, 'min': 0.0, 'max': 30.0, 'step': 0.01}), '高噪结束步': ('INT', {'default': 4, 'min': 1, 'max': 1000}), '低噪开始步': ('INT', {'default': 4, 'min': 0, 'max': 1000}), '采样器': (('euler', 'unipc', 'dpm++', 'dpm++_sde', 'ddim', 'flowmatch_causvid'), {'default': 'euler'})}, 'optional': {'源视频或源图': ('IMAGE',), '参考视频': ('IMAGE',), '参考图1': ('IMAGE',), '参考图2': ('IMAGE',), '参考图3': ('IMAGE',), '参考图4': ('IMAGE',), '参考图5': ('IMAGE',), '参考图6': ('IMAGE',), '参考图7': ('IMAGE',), '参考图8': ('IMAGE',), '参考图最大边': ('INT', {'default': 832, 'min': 16, 'max': 8192, 'step': 16}), '模型精度': (('bf16', 'fp16', 'fp32', 'fp16_fast'), {'default': 'bf16'}), '模型量化': (('disabled', 'fp8_e4m3fn', 'fp8_e4m3fn_scaled', 'fp8_e4m3fn_fast', 'fp8_e4m3fn_scaled_fast', 'fp8_e5m2', 'fp8_e5m2_scaled', 'fp8_e5m2_fast', 'fp8_e5m2_scaled_fast'), {'default': 'disabled'}), '注意力模式': (('sageattn', 'sdpa', 'flash_attn_2', 'flash_attn_3', 'sageattn_3', 'radial_sage_attention', 'sageattn_compiled'), {'default': 'sageattn'}), 'VAE精度': (('bf16', 'fp16', 'fp32'), {'default': 'bf16'}), '文本精度': (('bf16', 'fp32'), {'default': 'bf16'}), '文本量化': (('disabled', 'fp8_e4m3fn'), {'default': 'fp8_e4m3fn'}), '文本编码设备': (('gpu', 'cpu'), {'default': 'gpu'}), '强制卸载': ('BOOLEAN', {'default': True}), 'BlockSwap块数': ('INT', {'default': 30, 'min': 0, 'max': 40, 'step': 1})}}
        # --8<-- 契约结束 --8<--

    def generate(self, **kwargs):
        """Wan2.2 双噪声两阶段接力：文本编码 → Bernini 上下文 → 高噪模型采样 →
        低噪模型采样 → 解码。

        后端 te_bernini_backend/ 动态注册为 ``_te_image_bernini_backend_`` 包后延迟导入；
        无 ComfyUI/GPU 环境导入失败时抛「需要 ComfyUI 环境」。
        """
        try:
            wan = _wan_modules()
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError('需要 ComfyUI 环境（TE Bernini-R 内置后端加载失败：%s）' % exc) from exc

        def gi(chinese_name, english_name=None, default=None):
            value = _get_input(kwargs, chinese_name, english_name)
            return default if value is None else value

        # ---- 参数读取（中文键名为主，兼容英文别名） ----
        high_model = str(gi('高噪模型', 'high_noise_model',
                            'Wan22_Bernini_HIGH_fp8_e4m3fn_scaled.safetensors'))
        low_model = str(gi('低噪模型', 'low_noise_model',
                           'Wan22_Bernini_LOW_fp8_e4m3fn_scaled.safetensors'))
        vae_name = str(gi('VAE模型', 'vae_model', 'Wan2_1_VAE_bf16.safetensors'))
        text_encoder = str(gi('文本编码器', 'text_encoder', 'umt5-xxl-enc-fp8_e4m3fn.safetensors'))
        accel_enabled = bool(gi('启用加速LoRA', 'enable_accel_lora', True))
        high_lora = gi('高噪加速LoRA', 'high_accel_lora', LORA_NONE)
        high_lora_strength = float(gi('高噪LoRA强度', 'high_accel_lora_strength', 1.0))
        low_lora = gi('低噪加速LoRA', 'low_accel_lora', LORA_NONE)
        low_lora_strength = float(gi('低噪LoRA强度', 'low_accel_lora_strength', 1.0))
        prompt = str(gi('提示词', 'prompt', '') or '')
        negative_prompt = str(gi('负面提示词', 'negative_prompt', 'bad video') or '')
        width = int(gi('宽度', 'width', 832))
        height = int(gi('高度', 'height', 480))
        num_frames = int(gi('帧数', 'num_frames', 81))
        seed = int(gi('种子', 'seed', 666))
        steps = int(gi('步数', 'steps', 8))
        shift = float(gi('Shift', 'shift', 5.0))
        high_cfg = float(gi('高噪CFG', 'high_cfg', 1.0))
        low_cfg = float(gi('低噪CFG', 'low_cfg', 1.0))
        high_end_step = int(gi('高噪结束步', 'high_end_step', 4))
        low_start_step = int(gi('低噪开始步', 'low_start_step', 4))
        scheduler_name = str(gi('采样器', 'scheduler', 'euler'))
        source_video = gi('源视频或源图', 'source_video')
        reference_video = gi('参考视频', 'reference_video')
        reference_images = {index: gi('参考图%d' % index, 'reference_image_%d' % index)
                            for index in range(1, 9)}
        ref_max_size = int(gi('参考图最大边', 'ref_max_size', 832))
        model_precision = str(gi('模型精度', 'model_precision', 'bf16'))
        model_quantization = str(gi('模型量化', 'model_quantization', 'disabled'))
        attention_mode = str(gi('注意力模式', 'attention_mode', 'sageattn'))
        vae_precision = str(gi('VAE精度', 'vae_precision', 'bf16'))
        text_precision = str(gi('文本精度', 'text_precision', 'bf16'))
        text_quantization = str(gi('文本量化', 'text_quantization', 'fp8_e4m3fn'))
        text_device = str(gi('文本编码设备', 'text_device', 'gpu'))
        force_offload = bool(gi('强制卸载', 'force_offload', True))
        blocks_to_swap = int(gi('BlockSwap块数', 'blocks_to_swap', 30))

        # ---- 校验 ----
        if low_start_step > steps:
            raise ValueError('低噪开始步不能大于步数')
        if high_end_step > steps:
            raise ValueError('高噪结束步不能大于步数')
        # 解码分块（无节点参数，取后端 WanVideoDecode 默认值）
        decode_tile_x, decode_tile_stride_x = 272, 144
        decode_tile_y, decode_tile_stride_y = 272, 128
        if decode_tile_x <= decode_tile_stride_x:
            raise ValueError('解码分块X 必须大于 解码步长X')
        if decode_tile_y <= decode_tile_stride_y:
            raise ValueError('解码分块Y 必须大于 解码步长Y')

        # ---- 文本编码 ----
        _ensure_not_interrupted()
        _log('TE Bernini-R: encoding text')
        text_embeds, _negative_text_embeds, _display_prompt = \
            wan['WanVideoTextEncodeCached']().process(
                model_name=text_encoder, precision=text_precision,
                positive_prompt=prompt, negative_prompt=negative_prompt,
                quantization=text_quantization, use_disk_cache=True, device=text_device)

        # ---- VAE + Bernini 上下文 latents ----
        _ensure_not_interrupted()
        _log('TE Bernini-R: loading VAE')
        vae, = wan['WanVideoVAELoader']().loadmodel(model_name=vae_name, precision=vae_precision)

        has_context = (source_video is not None or reference_video is not None
                       or any(image is not None for image in reference_images.values()))
        _log('TE Bernini-R: building Bernini context latents')
        if has_context:
            context_kwargs = {}
            for index, image in reference_images.items():
                if image is not None:
                    context_kwargs['reference_image_%d' % index] = image
            image_embeds, = wan['WanAnimatePlusBernini']().process(
                vae=vae, width=width, height=height, num_frames=num_frames,
                source_video=source_video, reference_video=reference_video,
                ref_max_size=ref_max_size, force_offload=force_offload, tiled_vae=False,
                **context_kwargs)
        else:
            image_embeds, = wan['WanVideoEmptyEmbeds']().process(
                num_frames=num_frames, width=width, height=height)

        block_swap_args = _make_block_swap_args(blocks_to_swap)

        # ---- 高噪阶段 ----
        _ensure_not_interrupted()
        _log('TE Bernini-R: loading HIGH noise model')
        model, = wan['WanVideoModelLoader']().loadmodel(
            model=high_model, base_precision=model_precision, load_device='offload_device',
            quantization=model_quantization, attention_mode=attention_mode)
        high_accel = _select_accel_lora(accel_enabled, high_lora, DEFAULT_HIGH_ACCEL_LORA)
        if high_accel:
            _log('TE Bernini-R: applying HIGH acceleration LoRA: %s' % high_accel)
        model = _apply_block_swap_and_lora(wan, model, high_accel, high_lora_strength, block_swap_args)

        _ensure_not_interrupted()
        _log('TE Bernini-R: sampling HIGH stage(bernini-high)')
        high_scheduler, = wan['WanVideoSchedulerv2']().process(
            scheduler=scheduler_name, steps=steps, shift=shift,
            start_step=0, end_step=high_end_step, unique_id=None)
        high_samples, _high_denoised = wan['WanVideoSamplerv2']().process(
            model=model, image_embeds=image_embeds, shift=shift, steps=steps,
            cfg=high_cfg, seed=seed, scheduler=high_scheduler, riflex_freq_index=0,
            text_embeds=text_embeds, force_offload=force_offload,
            start_step=0, end_step=high_end_step)

        # ---- 低噪阶段 ----
        _ensure_not_interrupted()
        _log('TE Bernini-R: loading LOW noise model(bernini-low)')
        model, = wan['WanVideoModelLoader']().loadmodel(
            model=low_model, base_precision=model_precision, load_device='offload_device',
            quantization=model_quantization, attention_mode=attention_mode)
        low_accel = _select_accel_lora(accel_enabled, low_lora, DEFAULT_LOW_ACCEL_LORA)
        if low_accel:
            _log('TE Bernini-R: applying LOW acceleration LoRA: %s' % low_accel)
        model = _apply_block_swap_and_lora(wan, model, low_accel, low_lora_strength, block_swap_args)

        _ensure_not_interrupted()
        _log('TE Bernini-R: sampling LOW stage')
        low_scheduler, = wan['WanVideoSchedulerv2']().process(
            scheduler=scheduler_name, steps=steps, shift=shift,
            start_step=low_start_step, end_step=-1, unique_id=None)
        low_samples, _low_denoised = wan['WanVideoSamplerv2']().process(
            model=model, image_embeds=image_embeds, shift=shift, steps=steps,
            cfg=low_cfg, seed=seed, scheduler=low_scheduler, riflex_freq_index=0,
            text_embeds=text_embeds, samples=high_samples, force_offload=force_offload,
            start_step=low_start_step, end_step=-1)

        # ---- 解码 ----
        _ensure_not_interrupted()
        _log('TE Bernini-R: decoding samples')
        images, = wan['WanVideoDecode']().decode(
            vae=vae, samples=low_samples, enable_vae_tiling=False,
            tile_x=decode_tile_x, tile_y=decode_tile_y,
            tile_stride_x=decode_tile_stride_x, tile_stride_y=decode_tile_stride_y)

        status = ('TE Bernini-R 完成 | size=%dx%d | frames=%d | steps=%d | prompt=%s'
                  % (width, height, num_frames, steps, prompt[:48]))
        _log(status)
        return (images, status)

NODE_CLASS_MAPPINGS = {'TE_Bernini_Prompt_Enhancer': TEBerniniPromptEnhancer, 'TE_Bernini_R_Generator': TEBerniniRGenerator}
NODE_DISPLAY_NAME_MAPPINGS = {'TE_Bernini_Prompt_Enhancer': 'TE MAN Bernini 提示词增强(本地orAPI)', 'TE_Bernini_R_Generator': 'TE MAN Bernini'}
