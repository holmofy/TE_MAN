# -*- coding: utf-8 -*-
"""te_man_open · TE_MAN_MOSS

本文件由 tools/codegen_skeletons.py 自动生成骨架。
INPUT_TYPES 为与原版逐字段一致的真机契约；请实现各 FUNCTION 方法。
"""

class TEMossBoxNode:
    """TE MAN MOSS 增强边界框/增强提示词

    注册名: TE_image_pro_moss_box
    规格:   spec/TE_MAN_MOSS.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/MOSS'
    FUNCTION = 'compile'
    OUTPUT_NODE = True
    DESCRIPTION = '画布拖拽画框，选中后可编辑类型、文字、描述、调色板。可直接接「TE MAN MOSS 增强版式规划/增强提示词」的元素列表输出。'
    RETURN_TYPES = ('STRING', 'STRING', 'IMAGE')
    RETURN_NAMES = ('完整版式提示词', '元素列表', '版式预览图')

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'整图描述': ('STRING', {'multiline': True, 'default': '', 'tooltip': '不接「上游描述」时使用的整图描述，编译后成为 summary.caption。前端不显示这个输入框。'}), 'boxes': ('STRING', {'multiline': True, 'default': '[\n {\n  "role": "title",\n  "type": "text",\n  "text": "夏日音乐节",\n  "desc": "enormous cream serif capitals, centred",\n  "bbox": [\n   55,\n   70,\n   185,\n   930\n  ]\n },\n {\n  "role": "hero",\n  "type": "obj",\n  "desc": "stage truss silhouettes, crowd, warm haze",\n  "bbox": [\n   285,\n   50,\n   750,\n   950\n  ]\n }\n]', 'tooltip': '框列表 JSON，由画布自动维护。bbox 为 [ymin, xmin, ymax, xmax]，0-1000 整数，顺序与 ComfyUI 自带边界框一致。'}), 'width': ('INT', {'default': 1024, 'min': 256, 'max': 4096, 'step': 16}), 'height': ('INT', {'default': 1536, 'min': 256, 'max': 4096, 'step': 16})}, 'optional': {'上游元素列表': ('STRING', {'forceInput': True, 'tooltip': '接「TE MAN MOSS 增强版式规划/增强提示词」的元素列表。连接后首次运行会把框载入画布，之后以画布编辑为准；上游内容变了会重新载入。'}), '上游描述': ('STRING', {'forceInput': True, 'tooltip': '可接上游的整图描述。连接后优先使用它。'}), 'last_incoming': ('STRING', {'multiline': True, 'default': '', 'tooltip': '内部状态：上一次已经载入画布的上游元素列表，由节点自己维护。'})}}
        # --8<-- 契约结束 --8<--

    def compile(self, **kwargs):
        """TODO: 按 spec/TE_MAN_MOSS.md 实现。输入经 kwargs 传入。"""
        raise NotImplementedError

class TEMossLayoutNode:
    """TE MAN MOSS 增强版式规划/增强提示词

    注册名: TE_image_pro_moss_layout
    规格:   spec/TE_MAN_MOSS.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/MOSS'
    FUNCTION = 'plan'
    OUTPUT_NODE = True
    DESCRIPTION = '输入一句话，自动扩写文案与画面，并按选中版式生成边界框，输出可直接喂给 MOSS-Image 的 layout 提示词。扩写可用 CLIP、本地 llama.cpp 或 API；选「只扩写(无框位)」只输出整图描述，选「直出(不进行任何处理)」则 prompt 原样输出。描述可接到「TE MAN MOSS 边界框」的上游描述。'
    RETURN_TYPES = ('STRING', 'STRING', 'IMAGE', 'STRING')
    RETURN_NAMES = ('完整版式提示词', '元素列表', '版式预览图', '描述')

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'增强方式': (('CLIP', '本地 llama.cpp', 'API'), {'default': 'CLIP', 'tooltip': '扩写用哪个模型。三者互不影响，没选中的后端参数可以留空。'}), 'prompt': ('STRING', {'multiline': True, 'default': '一张音乐节海报', 'tooltip': '一句话需求。中文即可，模型会扩写成完整画面描述并保留中文文案。'}), '版式选择': (('竖版海报', '横版横幅', '方形', '自动排版(官方skill)', '只扩写(无框位)', '直出(不进行任何处理)'), {'default': '竖版海报', 'tooltip': '内置版式骨架，坐标按比例存，换画布尺寸不用重算；「自动排版(官方skill)」由模型给每个槽位写位置，seed 变了版式也会变；「只扩写(无框位)」只输出扩写后的整图描述，不产生元素列表；「直出(不进行任何处理)」不调任何模型，prompt 原样传给下游。'}), 'width': ('INT', {'default': 1024, 'min': 256, 'max': 4096, 'step': 16, 'tooltip': '输出画布宽度，必须是 16 的倍数。'}), 'height': ('INT', {'default': 1536, 'min': 256, 'max': 4096, 'step': 16, 'tooltip': '输出画布高度，必须是 16 的倍数。'}), 'max_length': ('INT', {'default': 4096, 'min': 256, 'max': 8192, 'step': 64, 'tooltip': 'CLIP 与本地 llama.cpp 的生成上限（新增 token）；API 模式不发送此限制。'}), 'seed': ('INT', {'default': 0, 'min': 0, 'max': 281474976710655, 'step': 1, 'tooltip': 'CLIP 与本地 llama.cpp 使用；API 模式忽略。'}), '输出语言': (('中文', '英文'), {'default': '中文', 'tooltip': '扩写出来的整图描述和元素描述用什么语言；JSON 字段、slot 名和 text/obj 结构值始终是英文。'}), '本地模型': (('（请把模型放到 models/LLM）',), {'tooltip': 'models/LLM 下的本地模型，仅「本地 llama.cpp」使用；其它方式不用管。'}), '生成后卸载本地模型': ('BOOLEAN', {'default': True, 'tooltip': '仅本地 llama.cpp。生成完就释放显存，避免和后面的 MOSS 出图抢显存；要连续调版式可以关掉。'}), 'api_base_url': ('STRING', {'default': 'https://teynex.com', 'multiline': False, 'tooltip': '仅 API 使用；按 OpenAI 兼容的 /responses 接口调用。'}), 'API模型(responses格式)': ('STRING', {'default': 'deepseek-v4.1-flash', 'multiline': False, 'tooltip': '仅 API 使用；填服务端 /responses 接口认识的模型名。'}), 'api_key': ('STRING', {'default': '', 'multiline': False, 'tooltip': '仅 API 使用；留空时读取 TE MAN 的 config.ini。'})}, 'optional': {'clip': ('CLIP', {'forceInput': True, 'tooltip': '增强方式为 CLIP 时使用；其它方式接着也没关系。'})}}
        # --8<-- 契约结束 --8<--

    def plan(self, **kwargs):
        """TODO: 按 spec/TE_MAN_MOSS.md 实现。输入经 kwargs 传入。"""
        raise NotImplementedError

NODE_CLASS_MAPPINGS = {'TE_image_pro_moss_box': TEMossBoxNode, 'TE_image_pro_moss_layout': TEMossLayoutNode}
NODE_DISPLAY_NAME_MAPPINGS = {'TE_image_pro_moss_box': 'TE MAN MOSS 增强边界框/增强提示词', 'TE_image_pro_moss_layout': 'TE MAN MOSS 增强版式规划/增强提示词'}
