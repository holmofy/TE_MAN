# -*- coding: utf-8 -*-
"""te_man_open.shared.task_runner —— task_runner.pyd 的纯 Python 复刻。

逆向规格: spec/task_runner.md（含末尾"动态 introspection 回填节"）。

统一的批次任务调度器：线程池并发、进度条与日志回调、ComfyUI 中断透传。
本模块无网络、无文件 IO，纯并发编排（与原版一致）。
"""

import logging
import os
import concurrent.futures
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from typing import Callable, List, Optional, TypeVar

try:  # ComfyUI 环境下直接复用官方中断异常（导入态，非常量态，见 spec 回填节 (b)）
    from comfy.model_management import InterruptProcessingException
except Exception:  # noqa: BLE001  纯 Python 环境回退
    class InterruptProcessingException(Exception):
        """comfy 不可用时的中断异常回退（与 comfy.model_management 同名异常对齐）。"""


__all__ = [
    "BatchGenerationRunner",
    "InterruptProcessingException",
    "FIRST_COMPLETED",
    "TaskType",
    "ResultType",
]

# 动态 introspection 实锤：模块级 FIRST_COMPLETED 为字符串回显值
# （CPython 中 concurrent.futures.FIRST_COMPLETED 本身即 "FIRST_COMPLETED" 字符串），
# 用作 concurrent.futures.wait(..., return_when=FIRST_COMPLETED)。

_LOGGER = logging.getLogger("te_man_open.task_runner")

TaskType = TypeVar("TaskType")
ResultType = TypeVar("ResultType")


def _throw_if_comfy_interrupted() -> None:
    """与 comfy.model_management 的中断机制联动；comfy 不可用时跳过。

    队列被取消（用户点中断）时抛出 InterruptProcessingException，向上传播。
    """
    try:
        from comfy import model_management  # 惰性导入
    except Exception:  # noqa: BLE001  非 ComfyUI 环境
        return
    throw = getattr(model_management, "throw_exception_if_interrupted", None)
    if callable(throw):
        throw()
        return
    ensure = getattr(model_management, "ensure_not_interrupted", None)
    if callable(ensure):
        ensure()


class BatchGenerationRunner:
    """统一的批次任务调度器，负责线程池并发、进度条与日志回调。"""

    def __init__(
        self,
        tasks: List[TaskType],
        worker_fn: Callable[[TaskType], ResultType],
        batch_size: Optional[int] = None,
        continue_on_error: bool = True,
        progress_bar: Optional[Callable[[int], object]] = None,
        logger=None,
    ) -> None:
        self.tasks: List[TaskType] = list(tasks)
        self.worker_fn = worker_fn
        self.batch_size = int(batch_size) if batch_size else len(self.tasks)
        self.continue_on_error = bool(continue_on_error)
        self.progress_bar = progress_bar
        self.logger = logger if logger is not None else _LOGGER
        self.should_stop = False
        #: clamp 后的最终并发数，由 run() 按任务数与 max_workers 计算
        self.actual_workers = 1

    # -- 对外入口 -----------------------------------------------------------

    def run(
        self,
        progress_callback: Optional[Callable[[ResultType, int, int, object], None]] = None,
        max_workers: Optional[int] = None,
        ensure_not_interrupted: Optional[Callable[[], None]] = None,
        timeout: float = 0.1,
        progress_bar: Optional[Callable[[int], object]] = None,
    ) -> List[ResultType]:
        """通过线程池或串行方式执行任务，并在每个结果返回时调用 progress_callback。

        - 默认走 ThreadPoolExecutor + FIRST_COMPLETED 事件循环并发；
          max_workers<=1 或任务数为 1 时回退串行。
        - progress_callback(result, index, total, task) 每完成一个结果即触发，
          index 为 1 起始的完成序号，第四参为该结果对应的任务本体。
        - 失败任务（continue_on_error=True 时）在结果列表中以 None 占位，
          保持与 self.tasks 的位置对齐。
        - ensure_not_interrupted 为调用方注入的零参中断检查回调，任务间隙调用；
          comfy.model_management 的中断检查始终额外执行（不可用则跳过）。
        - 中断 / continue_on_error=False 的异常向上抛出，未完成任务被 cancel。
        """
        total = len(self.tasks)
        if total == 0:
            return []
        self.should_stop = False

        step = self._build_progress_step(
            progress_bar if progress_bar is not None else self.progress_bar, total
        )

        if max_workers is None:
            max_workers = min(total, max(1, os.cpu_count() or 1))
        try:
            workers = max(1, min(int(max_workers), total))
        except (TypeError, ValueError):
            workers = 1
        self.actual_workers = workers

        if workers <= 1:
            return self._run_sequential(
                progress_callback=progress_callback,
                ensure_not_interrupted=ensure_not_interrupted,
                progress_step=step,
            )
        return self._run_parallel(
            progress_callback=progress_callback,
            ensure_not_interrupted=ensure_not_interrupted,
            timeout=timeout,
            progress_step=step,
        )

    # -- 内部实现 -----------------------------------------------------------

    @staticmethod
    def _build_progress_step(factory, total: int) -> Optional[Callable[[int], None]]:
        """把 progress_bar 工厂/回调归一为步进函数；comfy.utils.ProgressBar 惰性兜底。"""
        bar = None
        if callable(factory):
            try:
                bar = factory(total)  # 工厂语义：传入总数，返回进度对象
            except TypeError:
                bar = factory  # 已是步进回调/进度对象
        if bar is None:
            try:
                from comfy.utils import ProgressBar  # 惰性导入，失败则跳过

                bar = ProgressBar(total)
            except Exception:  # noqa: BLE001
                bar = None
        if bar is None:
            return None
        if hasattr(bar, "update"):
            return bar.update
        if callable(bar):
            return bar
        return None

    def _handle_task_error(self, index: int, task, exc: Exception) -> None:
        """单任务异常统一处理：记日志 + add_note，continue_on_error=False 时中止。"""
        if isinstance(exc, InterruptProcessingException):
            self.should_stop = True
            raise exc
        self.logger.error(
            "批次任务异常: 任务 %s/%s 执行失败: %s", index + 1, len(self.tasks), exc
        )
        add_note = getattr(exc, "add_note", None)
        if callable(add_note):
            try:
                add_note("TE MAN 批次任务 %s/%s 异常" % (index + 1, len(self.tasks)))
            except Exception:  # noqa: BLE001
                pass
        if not self.continue_on_error:
            self.should_stop = True
            raise exc

    def _run_parallel(
        self,
        progress_callback: Optional[Callable[[ResultType, int, int, object], None]] = None,
        ensure_not_interrupted: Optional[Callable[[], None]] = None,
        timeout: float = 0.1,
        progress_step: Optional[Callable[[int], None]] = None,
    ) -> List[ResultType]:
        """线程池路径：submit 全部任务，FIRST_COMPLETED 事件循环逐个收割。"""
        total = len(self.tasks)
        results: List[Optional[ResultType]] = [None] * total
        completed_count = 0
        future_to_task = {}
        executor = ThreadPoolExecutor(
            max_workers=self.actual_workers, thread_name_prefix="TEManBatch"
        )
        try:
            for index, task in enumerate(self.tasks):
                future_ref = executor.submit(self.worker_fn, task)
                future_to_task[future_ref] = index

            pending = set(future_to_task.keys())
            while pending and not self.should_stop:
                try:
                    if ensure_not_interrupted is not None:
                        ensure_not_interrupted()
                    _throw_if_comfy_interrupted()
                except InterruptProcessingException:
                    self.should_stop = True  # 中断后置位并取消在途任务
                    raise
                completed, pending = wait(
                    pending, timeout=timeout, return_when=FIRST_COMPLETED
                )
                for future in completed:
                    index = future_to_task[future]
                    task = self.tasks[index]
                    try:
                        result = future.result()
                    except Exception as exc:  # noqa: BLE001
                        # 中断或 continue_on_error=False 时在内部抛出
                        self._handle_task_error(index, task, exc)
                        continue
                    results[index] = result
                    completed_count += 1
                    if progress_step is not None:
                        progress_step(1)
                    if progress_callback is not None:
                        progress_callback(result, completed_count, total, task)
        finally:
            # 中断/异常后取消尚未开始的任务（cancel_futures 兼容旧版 Python）
            for future in future_to_task:
                future.cancel()
            try:
                executor.shutdown(wait=True, cancel_futures=True)
            except TypeError:  # Python < 3.9
                executor.shutdown(wait=True)
        return results

    def _run_sequential(
        self,
        progress_callback: Optional[Callable[[ResultType, int, int, object], None]] = None,
        ensure_not_interrupted: Optional[Callable[[], None]] = None,
        progress_step: Optional[Callable[[int], None]] = None,
        timeout: Optional[float] = None,
    ) -> List[ResultType]:
        """串行路径：按序逐个 worker_fn(task)，should_stop 置位后停止后续任务。"""
        total = len(self.tasks)
        results: List[Optional[ResultType]] = [None] * total
        completed_count = 0
        for index, task in enumerate(self.tasks):
            if self.should_stop:
                break
            try:
                if ensure_not_interrupted is not None:
                    ensure_not_interrupted()
                _throw_if_comfy_interrupted()
            except InterruptProcessingException:
                self.should_stop = True  # 中断后置位
                raise
            try:
                result = self.worker_fn(task)
            except Exception as exc:  # noqa: BLE001
                # 中断或 continue_on_error=False 时在内部抛出
                self._handle_task_error(index, task, exc)
                continue
            results[index] = result
            completed_count += 1
            if progress_step is not None:
                progress_step(1)
            if progress_callback is not None:
                progress_callback(result, completed_count, total, task)
        return results
