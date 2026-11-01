# -*- coding: utf-8 -*-
"""te_man_open · GPT_Image_2_Generator

本文件由 tools/codegen_skeletons.py 自动生成骨架。
INPUT_TYPES 为与原版逐字段一致的真机契约；请实现各 FUNCTION 方法。
"""

class TEGPTImage2SafePyNode:
    """TE MAN GPT Image 2 & 2.5

    注册名: TE_image_pro_gpt_image_2
    规格:   spec/GPT_Image_2_Generator.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/OpenAI'
    FUNCTION = 'generate_images'
    OUTPUT_NODE = True
    DESCRIPTION = '使用 gpt-image-2 通过 OpenAI Images API 进行文生图或图生图。'
    RETURN_TYPES = ('IMAGE', 'STRING')
    RETURN_NAMES = ('images', 'text')

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'prompt': ('STRING', {'multiline': True, 'default': '一只戴着墨镜的白色猫咪，电影感，细节丰富', 'tooltip': 'gpt-image-2 提示词'}), 'api_key': ('STRING', {'default': '', 'multiline': False, 'tooltip': 'API Key；留空则使用 config.ini 中配置'}), 'api_base_url': ('STRING', {'default': '', 'multiline': False, 'tooltip': '服务地址；留空则使用 config.ini 中配置'}), 'batch_size': ('INT', {'default': 1, 'min': 1, 'max': 8, 'tooltip': '生成批次数量；每个批次生成 1 张图'}), '分辨率(价格不同)': (('1K', '2K', '4K'), {'default': '1K', 'tooltip': '1K / 2K / 4K；分辨率不同,价格不同。'}), 'size': (('Auto', '1:1', '16:9', '9:16', '3:2', '2:3', '4:3', '3:4', '5:4', '4:5', '7:3', '3:7'), {'default': '16:9', 'tooltip': '选择需要生成的分辨率比例。'})}, 'optional': {'seed': ('INT', {'default': -1, 'min': -1, 'max': 102400, 'control_after_generate': True, 'tooltip': '仅用于 ComfyUI 工作流记录，不写入请求体。'}), 'image_1': ('IMAGE', {'tooltip': '参考/编辑输入图像 1（可选）'}), 'image_2': ('IMAGE', {'tooltip': '参考/编辑输入图像 2（可选）'}), 'image_3': ('IMAGE', {'tooltip': '参考/编辑输入图像 3（可选）'}), 'image_4': ('IMAGE', {'tooltip': '参考/编辑输入图像 4（可选）'}), 'image_5': ('IMAGE', {'tooltip': '参考/编辑输入图像 5（可选）'}), 'image_6': ('IMAGE', {'tooltip': '参考/编辑输入图像 6（可选）'}), 'image_7': ('IMAGE', {'tooltip': '参考/编辑输入图像 7（可选）'}), 'image_8': ('IMAGE', {'tooltip': '参考/编辑输入图像 8（可选）'}), 'image_9': ('IMAGE', {'tooltip': '参考/编辑输入图像 9（可选）'}), '线路选择': (('线路1', '线路2'), {'default': '线路1', 'tooltip': '线路1：1K 图生图走 edits 但模型保持 gpt-image-2，2K/4K 保持原线路。线路2：统一走 edits，且 1K 改用 gpt-image-2-1k。'}), '绕过代理': ('BOOLEAN', {'default': False, 'tooltip': '需要忽略系统代理/梯子时开启'}), '快捷功能': (('无', '白底三视图', '白底四视图', '九宫格[剧情]分镜', '九宫格[场景]分镜', '九宫格[导演]分镜', '四宫格[剧情]分镜', '四宫格[视角]分镜', '导演故事板', '黑白素写故事板'), {'default': '无', 'tooltip': '使用快捷功能生成。'}), '增强提示词输入': ('STRING', {'forceInput': True, 'tooltip': '连接上游文本后优先使用该内容；未连接时使用节点内的增强提示词框。'}), '模型选择': (('GPT Image 2', 'GPT Image 2.5'), {'default': 'GPT Image 2', 'tooltip': '选择 GPT Image 2 或 GPT Image 2.5 模型系列。'})}}
        # --8<-- 契约结束 --8<--

    def generate_images(self, **kwargs):
        """TODO: 按 spec/GPT_Image_2_Generator.md 实现。输入经 kwargs 传入。"""
        raise NotImplementedError

NODE_CLASS_MAPPINGS = {'TE_image_pro_gpt_image_2': TEGPTImage2SafePyNode}
NODE_DISPLAY_NAME_MAPPINGS = {'TE_image_pro_gpt_image_2': 'TE MAN GPT Image 2 & 2.5'}
