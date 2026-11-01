# -*- coding: utf-8 -*-
"""te_man_open · TE_MAN_Text_Tools

本文件由 tools/codegen_skeletons.py 自动生成骨架。
INPUT_TYPES 为与原版逐字段一致的真机契约；请实现各 FUNCTION 方法。
"""

class TEMANTextToolsNode:
    """TE MAN Text文本处理

    注册名: TE_image_pro_text_tools
    规格:   spec/TE_MAN_Text_Tools.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/Text'
    FUNCTION = 'process_text'
    OUTPUT_NODE = True
    RETURN_TYPES = ('STRING', 'STRING')
    RETURN_NAMES = ('text', 'json')

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'输入文本': ('STRING', {'multiline': True, 'default': '一个穿红色旗袍的女性站在雨夜霓虹街道，手持折扇，电影感光影', 'tooltip': '输入剧情、简短提示词或需要处理的文本'}), '快捷功能': (('9段分镜提示词', '扩写生图提示词', '扩写生视频提示词', '自定义'), {'default': '9段分镜提示词', 'tooltip': '选择要执行的一次性文本处理功能'}), 'api_key': ('STRING', {'default': '', 'multiline': False, 'tooltip': 'API Key；留空则读取 config.ini'}), 'api_base_url': ('STRING', {'default': '', 'multiline': False, 'tooltip': '服务地址，如 https://api.xxx.com；可填到 /v1 或 /v1/responses'}), 'model': ('STRING', {'default': 'gpt-5.5', 'multiline': False, 'tooltip': 'Responses API 模型名称，按你的中转/服务端支持填写'}), '画面比例': (('16:9', '9:16', '1:1', '4:3', '3:4', '4:5', '5:4', '21:9', '9:21'), {'default': '16:9', 'tooltip': '主要用于 9段分镜 的 grid_aspect_ratio 和提示词方向'}), '输出语言': (('中文', 'English'), {'default': '中文', 'tooltip': '控制非 9 段分镜功能的输出语言；9 段分镜固定中文'}), 'max_output_tokens': ('INT', {'default': 4096, 'min': 256, 'max': 32768, 'step': 256, 'tooltip': '最大输出 token，9段分镜建议 4096 或更高'}), 'temperature': ('FLOAT', {'default': 0.7, 'min': 0.0, 'max': 2.0, 'step': 0.05, 'tooltip': '创意程度；如果服务端模型不支持，可调回默认或更低'})}, 'optional': {'seed': ('INT', {'default': -1, 'min': -1, 'max': 2147483647, 'control_after_generate': True, 'tooltip': '仅用于 ComfyUI 触发重新执行，不会写入请求体'}), 'timeout_s': ('INT', {'default': 300, 'min': 30, 'max': 1800, 'tooltip': '请求超时时间（秒）'}), '绕过代理': ('BOOLEAN', {'default': False, 'tooltip': '需要忽略系统代理/梯子时开启'}), '快捷功能自定义': ('STRING', {'forceInput': True, 'tooltip': '快捷功能选择“自定义”时生效；输入内容会添加到用户提示词前面'})}}
        # --8<-- 契约结束 --8<--

    def process_text(self, **kwargs):
        """TODO: 按 spec/TE_MAN_Text_Tools.md 实现。输入经 kwargs 传入。"""
        raise NotImplementedError

NODE_CLASS_MAPPINGS = {'TE_image_pro_text_tools': TEMANTextToolsNode}
NODE_DISPLAY_NAME_MAPPINGS = {'TE_image_pro_text_tools': 'TE MAN Text文本处理'}
