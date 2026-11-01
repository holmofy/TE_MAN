# -*- coding: utf-8 -*-
"""te_man_open · Gemini_Imagen_Generator

本文件由 tools/codegen_skeletons.py 自动生成骨架。
INPUT_TYPES 为与原版逐字段一致的真机契约；请实现各 FUNCTION 方法。
"""

class BananaGeminiImageSafePyNode:
    """TE MAN Gemini Image

    注册名: TE_image_pro_banana
    规格:   spec/Gemini_Imagen_Generator.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/Gemini'
    FUNCTION = 'generate_images'
    OUTPUT_NODE = True
    RETURN_TYPES = ('IMAGE', 'STRING')
    RETURN_NAMES = ('images', 'text')

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'prompt': ('STRING', {'multiline': True, 'default': '一只可爱的小猫', 'tooltip': '生成图像的文本提示词，可多行描述内容、风格等'}), 'api_key': ('STRING', {'default': '', 'multiline': False, 'tooltip': '调用服务的 API Key；留空则优先使用 config.ini 中的配置'}), 'api_base_url': ('STRING', {'default': '', 'multiline': False, 'tooltip': 'API 服务地址；留空则使用 config.ini 中的配置'}), 'model_type': ('STRING', {'default': 'gemini-3.1-flash-image-preview', 'multiline': False, 'tooltip': '模型名称）'}), 'batch_size': ('INT', {'default': 1, 'min': 1, 'max': 8, 'tooltip': '一次请求中要生成的图片数量，范围 1~8'}), 'aspect_ratio': (('Auto', '1:1', '9:16', '16:9', '21:9', '2:3', '3:2', '3:4', '4:3', '4:5', '5:4'), {'default': 'Auto', 'tooltip': '生成图像的宽高比例，Auto 为由服务端自动决定'}), 'API格式': (('Gemini原生API', 'OpenAI Images API', 'OpenAI Chat API'), {'default': 'Gemini原生API', 'tooltip': '选择API格式：Gemini原生API | OpenAI Images API (/v1/images/*) | OpenAI Chat API (/v1/chat/completions)'})}, 'optional': {'seed': ('INT', {'default': -1, 'min': -1, 'max': 102400, 'control_after_generate': True, 'tooltip': '随机种子，-1 为自动随机；固定种子可复现同一输出'}), 'top_p': ('FLOAT', {'default': 0.95, 'min': 0.0, 'max': 1.0, 'step': 0.01, 'tooltip': '采样参数 Top-P，数值越低越保守，越高多样性越强'}), 'image_size': (('1K', '2K', '4K'), {'default': '2K', 'tooltip': '分辨率'}), 'image_1': ('IMAGE', {'tooltip': '参考图像 1，可为空；用于图生图或多图融合'}), 'image_2': ('IMAGE', {'tooltip': '参考图像 2，可为空；用于图生图或多图融合'}), 'image_3': ('IMAGE', {'tooltip': '参考图像 3，可为空；用于图生图或多图融合'}), 'image_4': ('IMAGE', {'tooltip': '参考图像 4，可为空；用于图生图或多图融合'}), 'image_5': ('IMAGE', {'tooltip': '参考图像 5，可为空；用于图生图或多图融合'}), 'image_6': ('IMAGE', {'tooltip': '参考图像 6，可为空；用于图生图或多图融合'}), 'image_7': ('IMAGE', {'tooltip': '参考图像 7，可为空；用于图生图或多图融合'}), 'image_8': ('IMAGE', {'tooltip': '参考图像 8，可为空；用于图生图或多图融合'}), 'image_9': ('IMAGE', {'tooltip': '参考图像 9，可为空；用于图生图或多图融合'}), '绕过代理': ('BOOLEAN', {'default': False, 'tooltip': '梯子速度不佳、不可靠时开启'}), '快捷功能': (('无', '白底三视图', '白底四视图', '九宫格[剧情]分镜', '九宫格[场景]分镜', '四宫格[剧情]分镜', '四宫格[视角]分镜'), {'default': '无', 'tooltip': '使用快捷功能生成。'})}}
        # --8<-- 契约结束 --8<--

    def generate_images(self, **kwargs):
        """TODO: 按 spec/Gemini_Imagen_Generator.md 实现。输入经 kwargs 传入。"""
        raise NotImplementedError

NODE_CLASS_MAPPINGS = {'TE_image_pro_banana': BananaGeminiImageSafePyNode}
NODE_DISPLAY_NAME_MAPPINGS = {'TE_image_pro_banana': 'TE MAN Gemini Image'}


class BananaGeminiAsyncSafePyNode:
    """TE MAN Gemini 特渠

    注册名: TE_image_pro_special_async2
    规格:   spec/Gemini_Imagen_Generator.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/Gemini'
    FUNCTION = 'generate_images'
    OUTPUT_NODE = True
    RETURN_TYPES = ('IMAGE', 'STRING')
    RETURN_NAMES = ('images', 'text')

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'prompt': ('STRING', {'multiline': True, 'default': '一只快乐的小猫', 'tooltip': '生成图像的文本提示词'}), 'api_key': ('STRING', {'default': '', 'multiline': False, 'tooltip': '调用服务的 API Key；留空则优先使用 config.ini 中的配置'}), 'api_base_url': ('STRING', {'default': '', 'multiline': False, 'tooltip': 'API 服务地址；留空则使用 config.ini 中的配置'}), 'model_type': (('nano-banana-pro', 'nano-banana-2'), {'default': 'nano-banana-pro', 'tooltip': '基础模型；会自动根据下方分辨率拼接实际请求模型名'}), 'batch_size': ('INT', {'default': 1, 'min': 1, 'max': 8, 'tooltip': '一次请求中要生成的图片数量，范围 1~8'}), 'aspect_ratio': (('1:1', '16:9', '9:16', '4:3', '3:4'), {'default': '4:3', 'tooltip': '宽高比'}), 'image_size': (('1K', '2K', '4K'), {'default': '1K', 'tooltip': '分辨率；会自动拼接到模型名称中'})}, 'optional': {'seed': ('INT', {'default': -1, 'min': -1, 'max': 102400, 'control_after_generate': True, 'tooltip': '随机种子，-1 为自动随机；固定种子可复现同一输出'}), 'image_1': ('IMAGE', {'tooltip': '参考图像 1，可为空；用于图生图或多图融合'}), 'image_2': ('IMAGE', {'tooltip': '参考图像 2，可为空；用于图生图或多图融合'}), 'image_3': ('IMAGE', {'tooltip': '参考图像 3，可为空；用于图生图或多图融合'}), 'image_4': ('IMAGE', {'tooltip': '参考图像 4，可为空；用于图生图或多图融合'}), 'image_5': ('IMAGE', {'tooltip': '参考图像 5，可为空；用于图生图或多图融合'}), 'image_6': ('IMAGE', {'tooltip': '参考图像 6，可为空；用于图生图或多图融合'}), 'image_7': ('IMAGE', {'tooltip': '参考图像 7，可为空；用于图生图或多图融合'}), 'image_8': ('IMAGE', {'tooltip': '参考图像 8，可为空；用于图生图或多图融合'}), 'image_9': ('IMAGE', {'tooltip': '参考图像 9，可为空；用于图生图或多图融合'}), '绕过代理': ('BOOLEAN', {'default': False, 'tooltip': '梯子速度不佳、不可靠时开启'}), '快捷功能': (('无', '白底三视图', '白底四视图', '九宫格[剧情]分镜', '九宫格[场景]分镜', '四宫格[剧情]分镜', '四宫格[视角]分镜'), {'default': '无', 'tooltip': '使用快捷功能生成。'})}}
        # --8<-- 契约结束 --8<--

    def generate_images(self, **kwargs):
        """TODO: 按 spec/Gemini_Imagen_Generator.md 实现。输入经 kwargs 传入。"""
        raise NotImplementedError

NODE_CLASS_MAPPINGS = {'TE_image_pro_special_async2': BananaGeminiAsyncSafePyNode}
NODE_DISPLAY_NAME_MAPPINGS = {'TE_image_pro_special_async2': 'TE MAN Gemini 特渠'}
