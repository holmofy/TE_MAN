# config_manager.pyd 逆向规格

> 来源：PE32+ x86-64, Cython 3.1.2 (abi3) 编译，`PyInit_config_manager`。静态分析（字符串/导入导出表/反汇编常量定位）。
> 置信度说明：[高] = 字符串直接证据；[中] = 强暗示推断；[低] = 猜测。

## 1. 模块定位

TE_MAN 插件的**内部配置支撑库**（在 `__init__.py` 的 `SKIP_MODULES` 中，不注册任何 ComfyUI 节点）。模块 docstring 原文：「**集中管理 Banana Gemini 节点的配置与测试模式逻辑**」。编译产物的 C 源路径为 `F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\config_manager.c`，对应模块限定名 `custom_nodes.TE_image.config_manager`（说明该插件曾名为 `TE_image`，后被改包为 TE_MAN）。下游消费者（字符串证据）：`GPT_Image_2_Generator.pyd`、`Gemini_Imagen_Generator.pyd`、`Grok_Image_Generator.pyd`（均引用 `ConfigManager` / `load_api_key` / `get_effective_api_base_url` / `sanitize_api_key` / `load_max_workers` 等）与 `api_client.pyd`（引用 `config_manager` / `sanitize_api_key`）。

## 2. Python API

- 导出：`PyInit_config_manager`（唯一导出符号）。
- 模块级公开对象：
  - **类 `ConfigManager`** [高]，构造参数 `base_dir`（限定名 `ConfigManager.__init__` 紧邻符号串 `base_dir` 出现）[高]；依据符号字符串推断的实例属性：`_base_dir`、`_config_path`、`_test_config_path` [高，符号字符串直接证据]。
  - 模块级常量 `MODULE_DIR` [高，符号字符串]。
- 完整方法清单 [高，均来自符号字符串与 traceback 局部名引用]：
  - `__init__(self, base_dir)` — `base_dir` 为空时回退到模块所在目录（证据：`MODULE_DIR` + `os.path.dirname(os.path.abspath(__file__))` 的 `dirname`/`abspath` 符号串）[中]
  - `_parse_bool(value)` — 布尔解析
  - `_clamp_cost_factor(cost_factor)` / `clamp_cost_factor(cost_factor)` —「对外暴露的 cost_factor 限幅接口」（原 docstring）
  - `_decode_api_base_url()`（含 genexpr）— XOR + base64 解码
  - `_get_default_base_url()`（含 genexpr）— 由码点数组拼出默认 URL
  - `_is_test_mode_enabled()` — 读环境变量开关
  - `_load_test_section()` / `_load_test_api_key()` / `_load_test_base_url()`
  - `_ensure_sample_config_exists()` — 生成示例配置
  - `_get_configured_base_url()` / `get_effective_api_base_url()` — URL 解析链
  - `sanitize_api_key(api_key)` — 规整并识别占位符
  - `load_api_key()`、`load_cost_factor()`、`load_max_workers()`、`load_network_workers_cap()`、`should_bypass_proxy()`
- 类型注解证据 [高，来自 PyArg 反射期间被构造的注解对象字符串]：`Optional[str]`、`Optional[float]`、`Optional[Dict[str, str]]`。
- Python 侧依赖 [高，全部为符号/属性字符串]：`configparser`（`ConfigParser`）、`re`、`os`（`environ`、`get`、`cpu_count`、`path.dirname/abspath/exists/join`—join 未直接核证）、`base64`（`b64decode`）、`typing`（`Optional`）、`.logger`（调用 `logger.info` / `logger.warning` / `logger.success`，对应本地明文 `logger.py`）、`sys`。
- **ComfyUI 节点注册：无**——文件中不存在 `NODE_CLASS_MAPPINGS` / `INPUT_TYPES` / `CATEGORY` 等字符串。

> 注：部分数值常量（默认 URL 码点、XOR 密钥分片、限幅边界）以 C 立即数形式嵌入 .text，静态提取不可靠（存在 objdump 无法引用到的取址偏移），相关结论按 [中] 处理并交叉比对 UTF-8/ASCII 字符串证据；无法落地的均标"未确认"。

## 3. 内部接口（非节点模块）

### 配置文件布局 [高]

- 主配置：模块目录下 `config.ini`（字符串 "config.ini"），节名 `_CONFIG_SECTION = "gemini"`（字符串 "gemini" + 根目录 config.ini 样例 `[gemini]` 互证）。
- 主配置键 [高，键名字符串]：`api_key`、`api_base_url`、`api_base_url_enc`（`_CONFIG_KEY_API_BASE_URL_ENC`）、`balance_cost_factor`、`max_workers`、`network_workers_cap`、`bypass_proxy`。
- 测试配置：`banana_gemini_test.local.ini`（`_TEST_CONFIG_FILE_NAME`），节名 `_TEST_CONFIG_SECTION = "gemini_test"`，键 `test_api_key`、`test_base_url` [高]。
- 测试模式总开关：环境变量 **`BANANA_GEMINI_USE_LOCAL_TEST`**（`_TEST_MODE_ENV_VAR`，`os.environ` + `.get`）[高]。

### ConfigManager 行为规格

1. **API Key 读取** `load_api_key` [高]：读 `[gemini] api_key`；经 `sanitize_api_key` 规整。
   - `sanitize_api_key` [高]：`re.sub(pattern, "", ...)` 正则 —— 源文件含模式字符串 **`[\s_-]+`**（删去全部空格/下划线/连字符），并与 `_PLACEHOLDER_KEYS` 对照识别占位符（占位符字符串证据：`your-api-key-here`、`yourapikeyhere`、`your_api_key_here`；清理后三者会归一成同一形态，暗示清理后需比对的正式值是 `yourapikeyhere` [中]）。命中/缺省时给出提示「请编辑文件并填入你的 API Key」并返回 None/占位值（具体返回值 未确认）。
2. **Effective Base URL 解析链** `get_effective_api_base_url` [中，顺序为推断]：
   - 测试模式开（env var 为真，`_parse_bool` 解析 true/false/yes 等，字符串证据 `true`/`false`/`yes`）→ 用测试配置的 `test_base_url`；
   - 否则 `_get_configured_base_url`：优先 `[gemini] api_base_url` 明文，其次 `[gemini] api_base_url_enc` 混淆值（`_decode_api_base_url` 解码）；
   - 最后回退 `_get_default_base_url()`：由 **`_DEFAULT_API_BASE_URL_CODEPOINTS`**（码点数组，字面量被刻意拆散防搜串）经 genexpr 逐 `chr(c)` 拼接 — `PyUnicode_FromOrdinal` 在 0x1800031e8 处有唯一调用点（反汇编证据）。由于码点既非 4/8 字节连续数组、也无邻近 `PyLong_FromLong` 调用簇，单个值无法静态摘出；**结合根目录 `config.ini` 样例 `api_base_url = https://teynex.com` 与 README「API 站：https://teynex.com」推断默认值即为该站，未确认**。
3. **XOR+Base64 解码** `api_base_url_enc` [高，机制级]：
   - `base64.b64decode` 取字节，与 `_ENC_KEY_PARTS` 衍生的密钥逐位 XOR（反汇编证据：`PyNumber_Xor` @ 0x180002b37 位于迭代器循环内；`PyNumber_InPlaceXor` @ 0x180002527 位于字节缓冲区就地写回循环），再按 `utf-8` 解为 `plain_url`。
   - 作用域：错误消息「解码测试配置中的 `api_base_url_enc` 失败」明确其主用途是**解码测试配置节**中的编码 URL [高]；主配置节是否同样走此逻辑 未确认。
   - **`_ENC_KEY_PARTS` 的具体值 未确认**（常量以 C 立即数形态嵌在 .text，静态提取不可靠；该混淆仅为轻量反检索，非安全机制——密钥与密文同文件携带）。
4. **限流参数** [高]：
   - `load_max_workers`：读 `max_workers`（`configparser.getint`）；缺省回退 `default_workers`，并以 `_clamp_cost_factor` 同款语义受 `cpu_limit`/`os.cpu_count` 约束（字符串 `cpu_count`/`cpu_limit`/`default_workers`/`default_cap`）。根目录 config.ini 样例值 `max_workers = 4`、`network_workers_cap = 4`。
   - `load_network_workers_cap`：读 `network_workers_cap`，回退 `default_cap`。
   - `load_cost_factor`：读 `balance_cost_factor`（`configparser.getfloat`，字符串证据 `getfloat`），经 `_clamp_cost_factor` 限幅；限幅边界值 未确认（`PyFloat_FromDouble`/`PyFloat_FromString`/`PyOS_string_to_double` 调用点均已定位但常量取不出——objdump 对该几行指令存在整行丢失）。
   - `should_bypass_proxy`：读 `bypass_proxy` 布尔键，供网络层绕过系统代理 [中，用途推断]。
5. **示例配置自举** `_ensure_sample_config_exists` [高]：若 `config.ini` 不存在则写出占位示例；成功记 `logger.success(f"已创建示例配置文件: {path}")`，失败报「创建配置文件失败: 」。

## 4. 外部依赖与副作用

- **文件系统** [高]：读/建 `<模块目录>\config.ini`、读 `<模块目录>\banana_gemini_test.local.ini`（后者为本地测试专用配置，按惯例不应入库）。
- **环境变量** [高]：`BANANA_GEMINI_USE_LOCAL_TEST`（假值语义由 `_parse_bool` 决定，支持 `false` 字面量）。
- **网络** [中，由消费方执行]：本模块自身 PE 导入表仅有 `python3.dll` / `KERNEL32.dll` / `VCRUNTIME140.dll` / `api-ms-win-crt-*.dll`，**无** WS2_32/ADVAPI32 —— 纯文件/字符串处理，不直接联网、不读写注册表；`should_bypass_proxy` 的结果是给下游（api_client/图像生成器）的提示。
- **配置金钥**：API Key 明文存于 `config.ini`，`sanitize_api_key` 只做形态规整与占位符识别，**无加密** [高]。

## 5. 错误处理与用户可见文案

[高] 全部为文件内字符串原文；均通过 `logger`（本包 `logger.py`）输出，`logger.xxx` 调用类型按语义标注 [中]。

| 消息 | 触发场景（推断） | 级别 |
|---|---|---|
| `读取配置文件失败: {e}` | `config.ini` 打开/解析异常 | error |
| `读取本地测试配置失败: {e}` | `banana_gemini_test.local.ini` 解析异常 | warning |
| `解码测试配置中的 api_base_url_enc 失败` | XOR/b64 解码抛异常 | warning |
| `请编辑文件并填入你的 API Key` | key 为占位符/缺失 | warning |
| `已创建示例配置文件: {path}` | 自举写出示例成功 | success |
| `创建配置文件失败: {e}` | 自举写出失败 | error |
| `读取 config 中的 max_workers 失败: {e}` | getint 异常 | warning/error |
| `读取 config 中的 network_workers_cap 失败: {e}` | getint 异常 | warning/error |
| `读取 config 中的 balance_cost_factor 失败: {e}` | getfloat 异常 | warning/error |
| `读取 config 中的 bypass_proxy 失败: {e}` | 解析异常 | warning/error |
| `读取 config 中的 api_base_url 失败: {e}` | 解析异常 | warning/error |

其余 docstring：「集中管理 Banana Gemini 节点的配置与测试模式逻辑」（模块级）、「对外暴露的 cost_factor 限幅接口」（`clamp_cost_factor`）。

## 6. 证据附录

关键字符串摘录（分组、去噪、保留原文，均直接取自 PE 内嵌数据）：

```
[模块身份]
PyInit_config_manager                  (唯一导出)
F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\config_manager.c
custom_nodes/TE_image/source_py_backup/config_manager.py
custom_nodes.TE_image.config_manager
集中管理 Banana Gemini 节点的配置与测试模式逻辑

[类与方法（符号字符串，成组出现）]
ConfigManager.__init__        base_dir
ConfigManager._parse_bool                 value
ConfigManager._decode_api_base_url(+genexpr)   plain_url / encoded / enc / encoding / utf-8
ConfigManager._get_default_base_url(+genexpr)  _DEFAULT_API_BASE_URL_CODEPOINTS
ConfigManager._is_test_mode_enabled       _TEST_MODE_ENV_VAR / BANANA_GEMINI_USE_LOCAL_TEST
ConfigManager._load_test_section          has_section / items
ConfigManager._load_test_api_key          test_api_key
ConfigManager._load_test_base_url         test_base_url
ConfigManager._ensure_sample_config_exists
ConfigManager._get_configured_base_url    _CONFIG_KEY_API_BASE_URL_ENC / api_base_url_enc
ConfigManager.get_effective_api_base_url  fallback / normalized
ConfigManager.sanitize_api_key            api_key / cleaned / _PLACEHOLDER_KEYS / [\s_-]+
ConfigManager.load_api_key
ConfigManager.load_cost_factor            balance_cost_factor / getfloat / clamp_cost_factor
ConfigManager.clamp_cost_factor           对外暴露的 cost_factor 限幅接口
ConfigManager.load_max_workers            max_workers / getint / cpu_count / default_workers / cpu_limit
ConfigManager.load_network_workers_cap    network_workers_cap / default_cap
ConfigManager.should_bypass_proxy         bypass_proxy

[常量与配置键]
_CONFIG_SECTION=gemini          _TEST_CONFIG_FILE_NAME=banana_gemini_test.local.ini
_TEST_CONFIG_SECTION=gemini_test
MODULE_DIR / _base_dir / _config_path / _test_config_path
config.ini / api_key / api_base_url / api_base_url_enc / balance_cost_factor
max_workers / network_workers_cap / bypass_proxy / test_api_key / test_base_url
_DEFAULT_API_KEY / _PLACEHOLDER_KEYS / your-api-key-here / yourapikeyhere / your_api_key_here

[消息]
读取配置文件失败:        请编辑文件并填入你的 API Key
读取本地测试配置失败:    解码测试配置中的 api_base_url_enc 失败
已创建示例配置文件:      创建配置文件失败:
读取 config 中的 max_workers 失败:            读取 config 中的 network_workers_cap 失败:
读取 config 中的 balance_cost_factor 失败:    读取 config 中的 bypass_proxy 失败:
读取 config 中的 api_base_url 失败:

[类型注解信号]
Optional[str] / Optional[float] / Optional[Dict[str, str]]

[下游引用（跨 pyd 的字符串）]
GPT_Image_2_Generator.pyd / Gemini_Imagen_Generator.pyd / Grok_Image_Generator.pyd
    → ConfigManager / load_api_key / get_effective_api_base_url / sanitize_api_key
      / load_max_workers（Gemini 侧含 load_network_workers_cap）
api_client.pyd → config_manager / sanitize_api_key

[反汇编常量定位（objdump -d + IAT 解析）]
PyNumber_Xor        @ 0x180002b37   ← genexpr 内逐字符 XOR
PyNumber_InPlaceXor @ 0x180002527   ← 缓冲区就位写回（bytearray 或 bytearray-like）
PyUnicode_FromOrdinal @ 0x1800031e8 ← 码点数组逐项 chr() 拼接
PyFloat_FromDouble / PyOS_string_to_double @ (限幅/fallback 求值，未提取常量)

[PE 导入表（负证据：纯文件/字符串处理）]
python3.dll / KERNEL32.dll / VCRUNTIME140.dll / api-ms-win-crt-runtime-l1-1-0.dll
（无 WS2_32 / ADVAPI32 /wininet 之类网络或注册表依赖）
```

### 配置样例（根目录 config.ini，明文参照）

```ini
[gemini]
api_key = you api_key
api_base_url = https://teynex.com

max_workers = 4
network_workers_cap = 4
```

（样例中 `api_key = you api_key` 属用户手填的占位值，非代码内置串；二进制内真正内置的占位键集合为 `yourapikeyhere` 一族 [高]。）
