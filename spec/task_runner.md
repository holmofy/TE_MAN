# task_runner.pyd 逆向规格

> 来源：PE32+ x86-64, Cython 3.1.2 (abi3) 编译，`PyInit_task_runner`。静态分析（字符串 / 导入导出表）。
> 置信度说明：[高] = 字符串直接证据；[中] = 强暗示推断；[低] = 猜测；"未确认" = 证据不足。

## 1. 模块定位

内部支撑库（`__init__.py:27` 将其列入 `SKIP_MODULES`，不作为节点加载）：**统一的批次任务调度器**。
提供 `BatchGenerationRunner` 类，供图像生成类节点做线程池并发提交、进度条/回调与 ComfyUI 中断透传，
对应 README.md:1 宣传的"多任务并发"能力。本模块自身无网络、无文件 IO，纯并发编排。
交叉引用：`BatchGenerationRunner` 与 `InterruptProcessingException` 字符串同时出现在
GPT_Image_2_Generator.pyd、Gemini_Imagen_Generator.pyd、Grok_Image_Generator.pyd 中（grep -l 实测），
即至少这三个生图节点是它的调用方 [高]（字符串在；import 关系本身未确认但可能性极高）。

## 2. Python API

- 导出：`PyInit_task_runner`（PE 导出表唯一导出符号）。
- 原始源码路径证据（编译时嵌入）：
  - `F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\task_runner.c`（Cython 生成物）
  - `custom_nodes/TE_image/source_py_backup/task_runner.py`（原始 .py 路径）
  - 原始包名为 `custom_nodes.TE_image`，现在打包为 TE_MAN。
- 模块级公开对象（qualname 字符串直接证据 [高]）：
  - `class BatchGenerationRunner` —— 类 docstring：`统一的批次任务调度器，负责线程池并发、进度条与日志回调`
  - 方法（qualname 全路径串）：`__init__`、`run`、`_run_parallel`、`_run_sequential`
  - `InterruptProcessingException` —— 异常类型名 [高]；是本模块定义还是从 `comfy.model_management` 导入：未确认
    （本模块有 `comfy.model_management` import 串，ComfyUI 的 model_management 自带同名中断异常，两者皆可能）。
  - `ensure_not_interrupted` —— 函数/回调名 [高]；它是本模块定义的函数还是调用方传入的回调（见 3.5），未确认。
    注意：四个方法都有全路径 qualname 串，而 `ensure_not_interrupted` 没有 → 更可能是**调用方注入的回调**或参数名 [中]。
  - `progress_bar_factory` —— 名字 [高]；角色未确认，推断为"传入总数、返回步进回调"的工厂（与注解 `Callable[[int], object]` 吻合）[低]。
- 类型注解串（typing 泛型，Cython 编译期嵌入，直接证明接口形状）[高]：
  - `Callable[[TaskType], ResultType]`（worker 函数）
  - `Callable[[ResultType, int, int, object], None]`（progress_callback）
  - `Callable[[int], object]`（progress_bar）
  - `Callable[[], None]`（零参回调，疑与中断检查相关）
  - `List[TaskType]`、`List[ResultType]`、`Optional`、`ResultType`、`TaskType`（TypeVar 名）
- ComfyUI 节点注册：**无** —— 全文无 `NODE_CLASS_MAPPINGS` / `INPUT_TYPES` / `RETURN_TYPES` / `CATEGORY` 字符串 [高]。

## 3. 内部接口（支撑库，非节点）

### 3.1 `BatchGenerationRunner.__init__`

实例属性名（直接字符串）[高]：`tasks`、`batch_size`、`actual_workers`、`worker_fn`、`continue_on_error`、
`should_stop`、`logger`、`progress_bar`。

推断签名 [中]（参数名=属性名集合；顺序与默认值未确认）：

```python
BatchGenerationRunner(
    tasks: List[TaskType],
    worker_fn: Callable[[TaskType], ResultType],
    batch_size: int,
    continue_on_error: bool,
    progress_bar: Callable[[int], object],   # 步进回调或进度条工厂产物，语义见 3.6
) -> None
```

- `max_workers` 串存在 [高]，可能是 `__init__` 或 `run` 的参数，归属未确认。
- `actual_workers`（与 `max_workers` 并存）推断为 clamp 后的最终并发数，如 `min(max_workers, len(tasks))` 之类 [低]。

### 3.2 `BatchGenerationRunner.run`

方法 docstring：`通过线程池或串行方式执行任务，并在每个结果返回时调用 progress_callback` [高]。

推断签名 [中]：

```python
run(
    progress_callback: Callable[[ResultType, int, int, object], None] | None = ...,
    max_workers: Optional[int] = ...,
    ...
) -> List[ResultType]
```

- `progress_callback` 参数在串池中以 ` progress_callback`（带前导空格，f-string 片段）形式也出现 [高]；
  注解四参 `(结果, int, int, object)` 的两个 int 推断为当前序号与总数，第四参推断为任务本体或上下文，具体语义未确认 [低]。
- `timeout` 串存在 [高]，疑为 `concurrent.futures.wait(..., timeout=...)` 或轮询间隔参数，归属未确认。

### 3.3 `_run_parallel`（线程池路径）

证据串 [高]：`ThreadPoolExecutor`、`concurrent.futures`、`submit`、`future`、`future_to_task`、`future_ref`、
`return_when`、`FIRST_COMPLETED`、`completed`、`pending`、`cancel_futures`、`shutdown`、`cancel`、`executor`。

推断流程 [中]：
1. `ThreadPoolExecutor(max_workers=actual_workers)` 创建线程池；
2. `executor.submit(worker_fn, task)` 提交全部任务，`future_to_task` 字典回查任务；
3. 循环 `concurrent.futures.wait(..., return_when=FIRST_COMPLETED)`（`completed`/`pending` 即 wait 的两个返回集合名；
   注：`wait` 一词本身 4 字符，被 `strings -n 5` 过滤，属合理缺失 [中]）；
4. 每完成一个 future 即取 `result()` 并调用 `progress_callback`；
5. 结束/异常时 `executor.shutdown(cancel_futures=True)` 取消未跑任务。

### 3.4 `_run_sequential`（串行路径）

证据串 [高]：`task`、`worker_fn`、`results`、`result`、`index`、`success`、`error`、`should_stop`、`progress_bar`。

推断流程 [中]：按序逐个 `worker_fn(task)`，结果 append 进 `results`，每个结果后推进度并回调；
`should_stop` 旗标置位后停止后续任务。`max_workers` 为 0/None 或任务过少时走此路径 [低]。

### 3.5 中断机制（ComfyUI 中断透传）

- `InterruptProcessingException` + `comfy.model_management`（两者都在本模块串池）[高]：
  推断执行间隙检查 ComfyUI 的中断状态，中断时抛/透传 `InterruptProcessingException` [中]
  （ComfyUI 的 `model_management.throw_exception_if_processing_interrupted()` 正是抛此异常；该调用串本身未出现，未确认）。
- `ensure_not_interrupted` [高]：中断检查的入口名。结合 `Callable[[], None]` 注解与"无全路径 qualname"两点，
  推断为**调用方传入的零参回调**（各节点自己封装检查逻辑），runner 在任务间隙调用它 [中]。
- 中断或错误后：`should_stop` 置位 + `cancel_futures`/`cancel` 取消在途任务 [中]。
- `add_note` 串 [高]：异常处理中使用 `exception.add_note(...)` 补充上下文 [中]。

### 3.6 日志与进度

- `logger` 属性 + `success`/`error` 串 [高]：推断调用 TE 自带 logger 的 `success`/`error` 方法
  （`__init__.py` 中明文可见同名方法用法）；`success`/`error` 也可能是状态键，未确认 [低]。
- 双层进度机制 [中]：`progress_bar: Callable[[int], object]`（每完成一步调用，`progress_bar_factory` 疑为其工厂）
  + `progress_callback`（结果级回调，含序号/总数）。
- `.rdata` 中有 double 常量 `0.1` 与 `1.0`（字节 `9A 99 99 99 99 99 B9 3F` / `00 00 00 00 00 00 F0 3F`）[高（字节实测）]；
  用途未确认，疑为超时/轮询间隔类参数默认值 [低]。

## 4. 外部依赖与副作用

- **无网络**：PE IMPORT 表仅 `python3.dll`、`KERNEL32.dll`、`VCRUNTIME140.dll`、`api-ms-win-crt-runtime-l1-1-0.dll`
  （pefile 实测）。无 WS2_32/WINHTTP —— 网络全部在 api_client.pyd 层，本模块只做编排 [高]。
- **无文件系统访问**：无路径串、无 config.ini 键名串 [高]。
- 运行时依赖：`concurrent.futures`（ThreadPoolExecutor/wait/FIRST_COMPLETED/cancel_futures）、`typing`、
  `comfy.model_management`（ComfyUI 核心）[高]。
- `inspect`、`types.MethodType`、`asyncio.coroutines` 等串为 Cython 运行时框架产物，非模块业务 import [中]。
- 第三方库：除 comfy 外无迹象 [高]。

## 5. 错误处理与用户可见文案

| 消息/名称 | 触发场景 | 置信度 |
|---|---|---|
| `批次任务异常: ` | 单个任务的 `worker_fn` 抛异常时的日志前缀（f-string），配合 `continue_on_error` 决定继续或中止 | [高]（原文串） |
| `InterruptProcessingException` | 用户在 ComfyUI 点中断后，批次执行被此异常打断并向上传播 | [高]（名字）/ 行为 [中] |
| `add_note` | 异常包装时补充说明 | [高]（名字） |

无其他中文用户可见文案；本模块不是节点，无显示名/tooltip。其余报错串
（如 `%s() got an unexpected keyword argument '%U'`）均为 Cython 调用协议通用消息，非业务逻辑 [高]。

## 6. 证据附录

以下摘录均为工具原始输出（strings -n 5 / UTF-8 扫描），未改写。

### 6.1 源路径与 qualname（ASCII）

```text
F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\task_runner.c
custom_nodes/TE_image/source_py_backup/task_runner.py
custom_nodes.TE_image.task_runner
custom_nodes.TE_image.task_runner.BatchGenerationRunner.__init__
custom_nodes.TE_image.task_runner.BatchGenerationRunner.run
custom_nodes.TE_image.task_runner.BatchGenerationRunner._run_parallel
custom_nodes.TE_image.task_runner.BatchGenerationRunner._run_sequential
Module 'task_runner' has already been imported. Re-initialisation is not supported.
Interpreter change detected - this module can only be loaded into one interpreter per process.
```

### 6.2 类型注解（ASCII）

```text
Callable[[TaskType], ResultType]
Callable[[ResultType, int, int, object], None]
Callable[[int], object]
Callable[[], None]
List[TaskType]
List[ResultType]
ResultType
TaskType
Optional
```

### 6.3 标识符（ASCII，去重分组）

```text
并发/线程:  ThreadPoolExecutor  executor  submit  future  future_to_task  future_ref
            completed  pending  return_when  FIRST_COMPLETED  cancel_futures  shutdown  cancel  timeout
任务/结果:  tasks  task  batch_size  worker_fn  results  result  index  success  error
控制:       should_stop  continue_on_error  ensure_not_interrupted  InterruptProcessingException  add_note
进度:       progress_bar  progress_bar_factory  progress_callback(另有 f-string 片段 " progress_callback")
其他:       logger  max_workers  actual_workers  cline_in_traceback  __test__
```

### 6.4 中文 docstring / 消息（UTF-8 扫描）

```text
统一的批次任务调度器，负责线程池并发、进度条与日志回调
通过线程池或串行方式执行任务，并在每个结果返回时调用 progress_callback
批次任务异常: 
```

### 6.5 数值常量（十六进制实测）

`.rdata` 中 `run`、`comfy` 等名附近：`9A 99 99 99 99 99 B9 3F`（double 0.1）、
`00 00 00 00 00 00 F0 3F`（double 1.0）。用途未确认。

### 6.6 复核命令

```bash
strings -n 5 /Users/holmofy/Downloads/TE_MAN/task_runner.pyd | grep -E 'BatchGenerationRunner|task_runner|Interrupt|ensure_not'
```
