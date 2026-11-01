# -*- coding: utf-8 -*-
"""te_man_open · Save_Image_With_Output

本文件由 tools/codegen_skeletons.py 自动生成骨架。
INPUT_TYPES 为与原版逐字段一致的真机契约；请实现各 FUNCTION 方法。
"""

class TESaveImageWithOutput:
    """TE MAN 加载图像&保存图像 Image

    注册名: TE_image_pro_save_image_with_output
    规格:   spec/Save_Image_With_Output.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/Utils'
    FUNCTION = 'save_images_and_output'
    OUTPUT_NODE = True
    DESCRIPTION = '保存输入图像到默认 output 或指定目录，同时将同一批图像继续从右侧输出，并支持普通、多图和全景预览。'
    RETURN_TYPES = ('IMAGE',)
    RETURN_NAMES = ('images',)

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'upload_image': (('', 'example.png'), {'default': '', 'image_upload': True, 'tooltip': '可选。左侧 images 未连接时，使用这里选择或上传的图像；左侧 images 一旦有输入，会优先覆盖这里的选择。要清空选择，请手动选回空白项。'}), 'filename_prefix': ('STRING', {'default': 'TE_MAN_%Y-%m-%d-%H-%M-%S', 'display_name': '文件名前缀', 'label': '文件名前缀', 'tooltip': '保存文件名/前缀。支持时间格式，例如 TE_MAN_%Y-%m-%d-%H-%M-%S。多张图会自动追加编号；需要接文本时请使用左侧「保存文件名」。'}), 'save_path': ('STRING', {'default': '默认', 'display_name': '保存位置', 'label': '保存位置', 'tooltip': '保存位置。默认或留空时保存到 ComfyUI 默认 output；填写时必须是绝对目录，例如 F:\\test\\images。'})}, 'optional': {'images': ('IMAGE', {'tooltip': '要保存并继续输出的图像。留空时会尝试使用本节点上一次保存过的图像。'}), '保存文件名': ('STRING', {'forceInput': True, 'tooltip': '可选。接入文本后会覆盖上方文件名前缀输入框，作为实际保存文件名。'}), '保存提示词': ('STRING', {'forceInput': True, 'tooltip': '可选。接入文本后，会用与图片相同的文件名在同目录保存 .txt。'})}, 'hidden': {'unique_id': 'UNIQUE_ID', 'prompt': 'PROMPT', 'extra_pnginfo': 'EXTRA_PNGINFO'}}
        # --8<-- 契约结束 --8<--

    def save_images_and_output(self, **kwargs):
        """TODO: 按 spec/Save_Image_With_Output.md 实现。输入经 kwargs 传入。"""
        raise NotImplementedError

NODE_CLASS_MAPPINGS = {'TE_image_pro_save_image_with_output': TESaveImageWithOutput}
NODE_DISPLAY_NAME_MAPPINGS = {'TE_image_pro_save_image_with_output': 'TE MAN 加载图像&保存图像 Image'}
