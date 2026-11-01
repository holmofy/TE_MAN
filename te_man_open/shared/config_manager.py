# -*- coding: utf-8 -*-
"""config_manager —— TE MAN 配置支撑库的纯 Python 复刻。

**集中管理 Banana Gemini 节点的配置与测试模式逻辑。**

依据 spec/config_manager.md（静态逆向 + Windows 真机 introspection 回填）实现：

- 主配置：``<MODULE_DIR>/config.ini`` 的 ``[gemini]`` 节
- 测试配置：``<MODULE_DIR>/banana_gemini_test.local.ini`` 的 ``[gemini_test]`` 节，
  由环境变量 ``BANANA_GEMINI_USE_LOCAL_TEST`` 启用
- ``get_effective_api_base_url`` 三级解析链：
  测试配置 test_base_url → 主配置 api_base_url / api_base_url_enc → 内置默认站
- 默认 API 站以码点数组存储（防明文检索），经 genexpr 逐 ``chr(c)`` 拼接
  （对应原版 ``PyUnicode_FromOrdinal`` 调用点）
- ``api_base_url_enc`` 为 base64 + 逐字节 XOR 轻量混淆（对应 ``PyNumber_InPlaceXor``
  就位写回循环）。``_ENC_KEY_PARTS`` 原版具体值未确认，此处按同格式实现；
  该混淆仅作反检索用途，密钥与密文同文件携带，**非安全机制**
- 配置缺失时自动写出占位示例文件；目录只读写不进时静默跳过
  （原版在写出失败时会记 ``创建配置文件失败: {e}``）

未确认项（与 spec 一致，按合理默认实现）：
- cost_factor 限幅边界（取 0.01 ~ 10.0）
- ``sanitize_api_key`` 命中占位符后的返回值（取 None）
- 主配置节 ``api_base_url_enc`` 是否走 XOR 解码（此处按同样处理）
"""

import base64
import configparser
import os
import re
from typing import Dict, Optional

# 模块所在目录（对应原版 pyd 所在的插件根目录；本包中即 te_man_open/，
# config.ini 与 banana_gemini_test.local.ini 均放在此目录下）
MODULE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ConfigManager:
    """集中管理 Banana Gemini 节点的配置与测试模式逻辑。"""

    # ==================== 配置文件布局 ====================
    _CONFIG_FILE_NAME = "config.ini"
    _CONFIG_SECTION = "gemini"
    _CONFIG_KEY_API_KEY = "api_key"
    _CONFIG_KEY_API_BASE_URL = "api_base_url"
    _CONFIG_KEY_API_BASE_URL_ENC = "api_base_url_enc"
    _CONFIG_KEY_BALANCE_COST_FACTOR = "balance_cost_factor"
    _CONFIG_KEY_MAX_WORKERS = "max_workers"
    _CONFIG_KEY_NETWORK_WORKERS_CAP = "network_workers_cap"
    _CONFIG_KEY_BYPASS_PROXY = "bypass_proxy"

    # ==================== 测试配置 ====================
    _TEST_CONFIG_FILE_NAME = "banana_gemini_test.local.ini"
    _TEST_CONFIG_SECTION = "gemini_test"
    _TEST_CONFIG_KEY_API_KEY = "test_api_key"
    _TEST_CONFIG_KEY_BASE_URL = "test_base_url"
    # 测试节同样支持 api_base_url_enc（spec：解码测试配置中的 api_base_url_enc 失败）
    _TEST_CONFIG_KEY_BASE_URL_ENC = "api_base_url_enc"
    _TEST_MODE_ENV_VAR = "BANANA_GEMINI_USE_LOCAL_TEST"

    # ==================== 占位 API Key ====================
    # 原版内置占位键集合为 yourapikeyhere 一族；三种原始形态经 [\s_-]+ 清理后
    # 归一为 yourapikeyhere
    _DEFAULT_API_KEY = "your-api-key-here"
    _PLACEHOLDER_KEYS_RAW = ("your-api-key-here", "yourapikeyhere", "your_api_key_here")
    _PLACEHOLDER_KEYS = frozenset(
        re.sub(r"[\s_-]+", "", _key).lower() for _key in _PLACEHOLDER_KEYS_RAW
    )

    # ==================== 默认 API 站 ====================
    # 码点数组存储，防明文检索；经 _get_default_base_url 的 genexpr 逐 chr(c) 拼接。
    # 原版码点未能从二进制静态摘出，此处按根目录 config.ini 样例与 README
    # （API 站：https://teynex.com）的推断值落地。
    _DEFAULT_API_BASE_URL_CODEPOINTS = (
        0x68, 0x74, 0x74, 0x70, 0x73, 0x3A, 0x2F, 0x2F,  # https://
        0x74, 0x65, 0x79, 0x6E, 0x65, 0x78, 0x2E,        # teynex.
        0x63, 0x6F, 0x6D,                                 # com
    )

    # ==================== XOR 混淆密钥分片 ====================
    # 原版 _ENC_KEY_PARTS 具体值未确认（C 立即数嵌入 .text，静态提取不可靠）；
    # 此处为同格式（bytes 序列 + 循环逐位 XOR）占位实现。仅作反检索，非安全机制。
    _ENC_KEY_PARTS = (0x37, 0x5A, 0x2E, 0x6B, 0x4F, 0x21, 0x58, 0x63)

    # ==================== cost_factor 限幅边界 ====================
    # 原版边界值未确认（PyFloat_FromDouble 常量取不出），取保守值。
    _MIN_COST_FACTOR = 0.01
    _MAX_COST_FACTOR = 10.0

    # ==================== 并发参数缺省值 ====================
    # 根目录 config.ini 样例：max_workers = 4、network_workers_cap = 4
    _DEFAULT_WORKERS = 4
    _DEFAULT_CAP = 4

    def __init__(self, base_dir: str = ""):
        """base_dir 为空时回退到模块所在目录（MODULE_DIR）。"""
        if not base_dir:
            base_dir = MODULE_DIR
        self._base_dir = base_dir
        self._config_path = os.path.join(base_dir, self._CONFIG_FILE_NAME)
        self._test_config_path = os.path.join(base_dir, self._TEST_CONFIG_FILE_NAME)
        self._ensure_sample_config_exists()

    # ==================== 内部工具 ====================
    @staticmethod
    def _parse_bool(value) -> bool:
        """布尔解析：支持 true/false/yes/no/1/0/on/off（大小写不敏感）。"""
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        return str(value).strip().lower() in ("true", "1", "yes", "on")

    def _get_config_value(self, key: str) -> Optional[str]:
        """读取主配置 [gemini] 节的原始字符串值。

        键缺失属正常缺省，静默返回 None；解析异常按 spec 记
        「读取配置文件失败: {e}」。
        """
        parser = configparser.ConfigParser()
        try:
            parser.read(self._config_path, encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            from .logger import logger
            logger.error(f"读取配置文件失败: {e}")
            return None
        try:
            value = parser.get(self._CONFIG_SECTION, key)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return None
        except Exception as e:  # noqa: BLE001
            from .logger import logger
            logger.warning(f"读取 config 中的 {key} 失败: {e}")
            return None
        return value

    # ==================== 示例配置自举 ====================
    def _ensure_sample_config_exists(self):
        """若 config.ini 不存在则写出占位示例；写不进（如只读安装目录）静默跳过。"""
        if os.path.exists(self._config_path):
            return
        sample = (
            f"[{self._CONFIG_SECTION}]\n"
            f"api_key = {self._DEFAULT_API_KEY}\n"
            "# api_base_url = https://teynex.com\n"
            "# api_base_url_enc = <base64+XOR 混淆的 API 站地址>\n"
            "balance_cost_factor = 1.0\n"
            "max_workers = 4\n"
            "network_workers_cap = 4\n"
            "bypass_proxy = false\n"
        )
        try:
            with open(self._config_path, "w", encoding="utf-8") as f:
                f.write(sample)
        except OSError:
            # 原版此处会记「创建配置文件失败: {e}」；本复刻在只读目录下静默跳过
            return
        from .logger import logger
        logger.success(f"已创建示例配置文件: {self._config_path}")

    # ==================== 测试模式 ====================
    def _is_test_mode_enabled(self) -> bool:
        """读环境变量开关 BANANA_GEMINI_USE_LOCAL_TEST。"""
        return self._parse_bool(os.environ.get(self._TEST_MODE_ENV_VAR, ""))

    def get_test_mode(self) -> bool:
        """是否处于本地测试模式（公开辅助接口）。"""
        return self._is_test_mode_enabled()

    def _load_test_section(self) -> Optional[Dict[str, str]]:
        """读取测试配置 [gemini_test] 节，返回键值字典；不存在/异常返回 None。"""
        if not os.path.exists(self._test_config_path):
            return None
        parser = configparser.ConfigParser()
        try:
            parser.read(self._test_config_path, encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            from .logger import logger
            logger.warning(f"读取本地测试配置失败: {e}")
            return None
        if not parser.has_section(self._TEST_CONFIG_SECTION):
            return None
        return dict(parser.items(self._TEST_CONFIG_SECTION))

    def _load_test_api_key(self) -> Optional[str]:
        """读取测试配置中的 test_api_key（经 sanitize 规整）。"""
        section = self._load_test_section()
        if not section:
            return None
        return self.sanitize_api_key(section.get(self._TEST_CONFIG_KEY_API_KEY))

    def _load_test_base_url(self) -> str:
        """读取测试配置中的 test_base_url，缺省时尝试 api_base_url_enc 解码。"""
        section = self._load_test_section()
        if not section:
            return ""
        url = (section.get(self._TEST_CONFIG_KEY_BASE_URL) or "").strip()
        if url:
            return url
        encoded = (section.get(self._TEST_CONFIG_KEY_BASE_URL_ENC) or "").strip()
        if encoded:
            try:
                decoded = self._decode_api_base_url(encoded)
            except Exception:  # noqa: BLE001
                decoded = ""
            if decoded:
                return decoded
            from .logger import logger
            logger.warning("解码测试配置中的 api_base_url_enc 失败")
        return ""

    # ==================== Base URL 解析 ====================
    @staticmethod
    def _decode_api_base_url(encoded: str) -> str:
        """XOR + base64 解码（PyNumber_InPlaceXor 就位写回语义）。"""
        if not encoded:
            return ""
        buf = bytearray(base64.b64decode(encoded))
        key = ConfigManager._ENC_KEY_PARTS
        for i in range(len(buf)):
            buf[i] ^= key[i % len(key)]
        return buf.decode("utf-8")

    @staticmethod
    def _get_default_base_url() -> str:
        """由码点数组经 genexpr 逐 chr(c) 拼出默认 URL（PyUnicode_FromOrdinal 语义）。"""
        return "".join(chr(c) for c in ConfigManager._DEFAULT_API_BASE_URL_CODEPOINTS)

    def _get_configured_base_url(self) -> str:
        """主配置节解析：优先 api_base_url 明文，其次 api_base_url_enc 混淆值。"""
        value = self._get_config_value(self._CONFIG_KEY_API_BASE_URL)
        if value is not None and value.strip():
            return value.strip()
        encoded = self._get_config_value(self._CONFIG_KEY_API_BASE_URL_ENC)
        if encoded is not None and encoded.strip():
            try:
                decoded = self._decode_api_base_url(encoded.strip())
            except Exception:  # noqa: BLE001
                decoded = ""
            if decoded:
                return decoded
            from .logger import logger
            logger.warning("解码测试配置中的 api_base_url_enc 失败")
        return ""

    def get_effective_api_base_url(self, default: str = "") -> str:
        """三级解析链：测试配置 → 配置节 → 内置默认站。

        ``default`` 为调用方提供的回退值：三级链前两级均未命中且传入了非空
        ``default`` 时返回 ``default``，否则返回内置默认站。
        """
        if self._is_test_mode_enabled():
            url = self._load_test_base_url()
            if url:
                return url
        configured = self._get_configured_base_url()
        if configured:
            return configured
        if default:
            return default
        return self._get_default_base_url()

    # ==================== API Key ====================
    def sanitize_api_key(self, api_key: Optional[str]) -> Optional[str]:
        """规整 API Key：删去全部空格/下划线/连字符，并识别占位键。

        命中占位符或缺省时提示「请编辑文件并填入你的 API Key」并返回 None
        （原版返回值未确认，此处取 None）。
        """
        if not api_key:
            from .logger import logger
            logger.warning("请编辑文件并填入你的 API Key")
            return None
        cleaned = re.sub(r"[\s_-]+", "", api_key)
        if not cleaned or cleaned.lower() in self._PLACEHOLDER_KEYS:
            from .logger import logger
            logger.warning("请编辑文件并填入你的 API Key")
            return None
        return cleaned

    def load_api_key(self) -> Optional[str]:
        """读取 [gemini] api_key 并规整；测试模式优先读 test_api_key。"""
        if self._is_test_mode_enabled():
            key = self._load_test_api_key()
            if key:
                return key
        return self.sanitize_api_key(self._get_config_value(self._CONFIG_KEY_API_KEY))

    # ==================== 限流参数 ====================
    def clamp_cost_factor(self, cost_factor: Optional[float]) -> Optional[float]:
        """对外暴露的 cost_factor 限幅接口。"""
        if cost_factor is None:
            return None
        try:
            value = float(cost_factor)
        except (TypeError, ValueError):
            return None
        return min(max(value, self._MIN_COST_FACTOR), self._MAX_COST_FACTOR)

    def load_cost_factor(self, default_cost_factor: float = 1.0) -> Optional[float]:
        """读取 [gemini] balance_cost_factor（getfloat）并经限幅。"""
        value = self._get_config_value(self._CONFIG_KEY_BALANCE_COST_FACTOR)
        if value is None:
            return self.clamp_cost_factor(default_cost_factor)
        try:
            return self.clamp_cost_factor(float(value))
        except (TypeError, ValueError) as e:
            from .logger import logger
            logger.warning(f"读取 config 中的 balance_cost_factor 失败: {e}")
            return self.clamp_cost_factor(default_cost_factor)

    def get_max_workers(self, default_workers: int = _DEFAULT_WORKERS) -> int:
        """读取 [gemini] max_workers（getint），缺省回退 default_workers，
        并按 os.cpu_count() 封顶、下限 1。"""
        cpu_limit = os.cpu_count() or 1
        workers = default_workers
        value = self._get_config_value(self._CONFIG_KEY_MAX_WORKERS)
        if value is not None:
            try:
                workers = int(value)  # 对应原版 configparser.getint
            except (TypeError, ValueError) as e:
                from .logger import logger
                logger.warning(f"读取 config 中的 max_workers 失败: {e}")
                workers = default_workers
        try:
            workers = int(workers)
        except (TypeError, ValueError):
            workers = default_workers
        return max(1, min(workers, cpu_limit))

    def get_network_workers_cap(self, default_cap: int = _DEFAULT_CAP) -> int:
        """读取 [gemini] network_workers_cap（getint），缺省回退 default_cap，
        并按 os.cpu_count() 封顶、下限 1。"""
        cpu_limit = os.cpu_count() or 1
        cap = default_cap
        value = self._get_config_value(self._CONFIG_KEY_NETWORK_WORKERS_CAP)
        if value is not None:
            try:
                cap = int(value)  # 对应原版 configparser.getint
            except (TypeError, ValueError) as e:
                from .logger import logger
                logger.warning(f"读取 config 中的 network_workers_cap 失败: {e}")
                cap = default_cap
        try:
            cap = int(cap)
        except (TypeError, ValueError):
            cap = default_cap
        return max(1, min(cap, cpu_limit))

    def is_bypass_proxy(self) -> bool:
        """读取 [gemini] bypass_proxy 布尔键，供网络层绕过系统代理。"""
        value = self._get_config_value(self._CONFIG_KEY_BYPASS_PROXY)
        if value is None:
            return False
        try:
            return self._parse_bool(value)
        except Exception as e:  # noqa: BLE001
            from .logger import logger
            logger.warning(f"读取 config 中的 bypass_proxy 失败: {e}")
            return False

    # ==================== 原版方法名别名 ====================
    # 真机符号名为 load_max_workers / load_network_workers_cap / should_bypass_proxy，
    # 保留别名以兼容按原版 API 调用的下游。
    load_max_workers = get_max_workers
    load_network_workers_cap = get_network_workers_cap
    should_bypass_proxy = is_bypass_proxy


# ==================== 模块级单例 ====================
CONFIG_MANAGER = ConfigManager()


# ==================== 导出 ====================
__all__ = ["ConfigManager", "CONFIG_MANAGER", "MODULE_DIR"]
