"""
Althea - Backend

"""
# Created 2022-2024 by James Bishop (james@bishopdynamics.com)
# License: GPLv3, see License.txt

from __future__ import annotations

import sys

from typing import Union
from traceback import print_exc

from multiprocessing import Queue, Process
from multiprocessing import Event as ProcessEvent
from multiprocessing import Manager as ProcessManager
from multiprocessing import Lock as ProcessLock

from threading import Thread
from threading import Event as ThreadEvent

from .common import time_nano, time, log, Any, Callable, dataclass, format_exc, IdProvider, Literal, LogEmulator, TYPE_CHECKING

from .scriptrunner import ScriptManager

if TYPE_CHECKING:
    from .nodes.base import Node, NodeConfig, CommonNodeConfig


class BackendException(Exception):
    """exception specific to backend"""


class KillableThread(Thread):
    """A thread with a kill method to force it to stop"""

    def __init__(self, *args, **keywords):
        Thread.__init__(self, *args, **keywords)
        self.killed = False

    def start(self):
        self.__run_backup = self.run  # pylint: disable=attribute-defined-outside-init
        self.run = self.__run
        Thread.start(self)

    def __run(self):
        sys.settrace(self.globaltrace)
        self.__run_backup()
        self.run = self.__run_backup

    def globaltrace(self, _frame, event, _arg):
        """do a global trace"""
        if event == 'call':
            return self.localtrace
        else:
            return None

    def localtrace(self, _frame, event, _arg):
        """do a local trace"""
        if self.killed:
            if event == 'line':
                raise SystemExit()
        return self.localtrace

    def kill(self):
        """Kill this thread"""
        self.killed = True


@dataclass
class CalcJob:
    """Calculation Job"""
    inputs: list[Any]  # input data
    node_type: type[Node]  # type of node (the actual class)
    node_config: NodeConfig
    node_common_config: CommonNodeConfig
    node_id: int
    job_id: int = 0  # will be set internally, 0 = unset


@dataclass
class CalcJobResult:
    """Result of a Calculation Job"""
    job_id: int  # matching calcjob
    node_id: int
    outputs: list[Any]  # output data
    duration: float  # ms, how long calculation took to perform
    error: bool = False
    error_message: str = ''
    error_traceback: str = ''
    log_messages: list[tuple[Literal['debug', 'info', 'warning', 'error'], str]] = None


class WorkerResources:
    """The resources provided to worker so they can handle jobs"""

    def __init__(self, job_queue: 'Queue[CalcJob]', results_queue: 'Queue[CalcJobResult]', stopper: ThreadEvent, is_process: bool, worker_name: str, script_cache: list, cache_lock: Any) -> None:
        self.job_queue = job_queue
        self.results_queue = results_queue
        self.stopper = stopper
        self.is_process = is_process
        self.worker_name = worker_name
        self.script_cache = script_cache
        self.cache_lock = cache_lock


class BackendConfig:
    """static global config values for backend"""
    process_sleep_time: float = 0.0001  # seconds, time to wait between checking empty queue
    wait_increment: float = 0.1  # seconds, how long for "wait for this" scenarios to wait before checking again
    wait_stop: int = 4  # seconds, how long to wait for worker processes to stop before killing


def handle_job_standard(job: CalcJob):
    """Handle a standard job"""
    t_start = time_nano()
    try:
        # log.debug(f'Picked up job: {job.job_id}')
        outputs = job.node_type.execute(job.inputs, job.node_config, job.node_common_config)
    except Exception as ex:
        duration = time_nano() - t_start
        result = CalcJobResult(job.job_id, job.node_id, [], duration, True, str(ex), format_exc())
    else:
        duration = time_nano() - t_start
        result = CalcJobResult(job.job_id, job.node_id, outputs, duration)
    return result


def handle_job_script(job: CalcJob, script_mgr: ScriptManager):
    """Handle a job that runs a script"""
    t_start = time_nano()
    script_content = job.node_config.get('script')
    result = script_mgr.run_script(script_content, job.inputs, job.node_id)
    duration = time_nano() - t_start
    log.debug(f'script execution took {duration}ns')
    if result.error:
        result = CalcJobResult(job.job_id, job.node_id, [], duration, True, result.error_message, result.error_traceback, log_messages=result.log_messages)
    else:
        result = CalcJobResult(job.job_id, job.node_id, result.outputs, duration, log_messages=result.log_messages)
    return result


def worker_function(resources: WorkerResources):
    """
    Worker function, which processes the job queue
        this is what runs inside thread/processes for each worker
    """
    worker_type = 'thread'
    if resources.is_process:
        worker_type = 'process'

    def shutdown():
        """quit this thread/process right now"""
        log.debug(f'[{resources.worker_name}] ({worker_type}) Shutting down')
        sys.exit()

    log.debug(f'[{resources.worker_name}] ({worker_type}) Starting up')
    script_mgr = ScriptManager(resources.script_cache, resources.cache_lock)
    try:
        while not resources.stopper.is_set():
            if resources.stopper.is_set():
                break
            try:
                # The most reliable way to kill this thread/process, is to call .close() on the job_queue
                #   which will cause an exception to be raised here and then it will die properly
                #   otherwise it will hang and ignore the stopper
                q_empty = resources.job_queue.empty()
            except Exception:
                break  # quit if the queue is dead
            if not q_empty:
                try:
                    job = resources.job_queue.get()
                except Exception as jex:
                    log.warning('Error while getting job from job_queue, assuming queue is gone and shutting down; this is a sign that backend was not shut down properly')
                    log.warning(f'Error was: {jex}')
                    break

                if job.node_type.__name__ == 'Node_PythonScript':
                    # Special handling for PythonScript, because it handles its own exception catching and traceback generation
                    result = handle_job_script(job, script_mgr)
                else:
                    result = handle_job_standard(job)
                resources.results_queue.put(result)
            else:
                time.sleep(BackendConfig.process_sleep_time)
    except BaseException as bex:
        print(f'Exception in backend process: {bex}')
        print_exc()
        shutdown()

    # if we got here, shutdown anyway
    shutdown()


class Backend:
    """Backend Implementation"""
    max_wait_stop: int = 4000  # milliseconds, how long to wait for workers

    def __init__(self, num_workers: int = 1, workers_as_processes: bool = True) -> None:
        log.info('Initializing backend...')
        self.job_queue: 'Queue[CalcJob]' = Queue()
        self.results_queue: 'Queue[CalcJobResult]' = Queue()
        self.num_workers = num_workers
        self.workers_as_processes = workers_as_processes
        self.workers: list[Union[KillableThread, Process]] = []
        self.stopper = None
        self.callbacks: dict[int, Callable[[CalcJobResult]]] = {}
        self.id_provider = IdProvider(10)
        self._mgr = ProcessManager()
        self.script_cache = self._mgr.list()
        self.script_cache_lock = ProcessLock()

    # public (run on main thread)

    def start(self):
        """Start backend service"""
        if self.workers_as_processes:
            log.info('Starting workers (processes)')
        else:
            log.info('Starting workers (threads)')

        if self.workers_as_processes:
            self.stopper = ProcessEvent()
        else:
            self.stopper = ThreadEvent()

        for i in range(1, self.num_workers + 1):
            worker_name = f'AltheaWorker-{i}'
            if self.workers_as_processes:
                # workers are processes
                resrcs = WorkerResources(
                    job_queue=self.job_queue,
                    results_queue=self.results_queue,
                    stopper=self.stopper,
                    is_process=True,
                    worker_name=worker_name,
                    script_cache=self.script_cache,
                    cache_lock=self.script_cache_lock)
                self.workers.append(Process(target=worker_function, name=worker_name, args=(resrcs,), daemon=True))
            else:
                # workers are threads
                resrcs = WorkerResources(
                    job_queue=self.job_queue,
                    results_queue=self.results_queue,
                    stopper=self.stopper,
                    is_process=False,
                    worker_name=worker_name,
                    script_cache=self.script_cache,
                    cache_lock=self.script_cache_lock)
                self.workers.append(KillableThread(target=worker_function, name=worker_name, args=(resrcs,), daemon=True))
            self.workers[-1].start()
            log.debug(f'Started worker: {worker_name}')

        log.debug('Waiting for workers to be ready')
        for wk in self.workers:
            while not wk.is_alive():
                time.sleep(BackendConfig.wait_increment)

        log.info('Workers are ready')

    def stop(self):
        """Stop backend service"""
        if self.workers_as_processes:
            log.info('Shutting down workers (processes)')
        else:
            log.info('Shutting down workers (threads)')

        # signal workers to stop voluntarily
        self.stopper.set()
        # give them a moment to stop on their own
        time.sleep(0.2)

        # NOTE: closing the job queue seems to be the only reliable way to kill off both threads and processes
        self.job_queue.close()
        self.results_queue.close()

        waited = 0
        if self.workers_as_processes:
            # workers are processes, lets try to wait til they stop properly
            log.info('Waiting for worker processes to stop...')
            for wk in self.workers:
                while wk.is_alive():
                    wk.terminate()
                    waited += 100
                    time.sleep(0.1)
                    if waited > self.max_wait_stop:
                        break
                if waited > self.max_wait_stop:
                    break
        else:
            # workers are threads
            log.info('Waiting for worker threads to stop...')
            for wk in self.workers:
                while wk.is_alive():
                    wk.kill()
                    waited += 100
                    time.sleep(0.1)
                    if waited > self.max_wait_stop:
                        break
                if waited > self.max_wait_stop:
                    break
                wk.join()
        if waited > self.max_wait_stop:
            log.warning('Workers took too long to shutdown on their own, stopping them forcibly')
        # we do not need to do anything to stop them, they will be killed off when the main thread exits

    def restart(self, num_workers: int = 1, workers_as_processes: bool = True):
        """Stop all workers, optionally adjust parameters, and start them up again"""
        log.info('Restarting backend...')
        self.stop()
        time.sleep(0.1)
        self.job_queue: 'Queue[CalcJob]' = Queue()
        self.results_queue: 'Queue[CalcJobResult]' = Queue()
        self.num_workers = num_workers
        self.workers_as_processes = workers_as_processes
        self.stopper.clear()
        self.id_provider.reset()
        self.workers.clear()
        self.start()

    def submit(self, job: CalcJob, callback: Callable[[CalcJobResult]]):
        """Submit a calculation job with a callback"""
        job.job_id = self.id_provider.next_id()
        self.callbacks[job.job_id] = callback
        self.job_queue.put(job)
        # log.debug(f'Queued job: {job.job_id}')

    def check(self):
        """Check if there are any results available, and call their callbacks"""
        while not self.results_queue.empty():
            result = self.results_queue.get()
            # log.debug(f'Returning result for job: {result.job_id}')
            LogEmulator.process_messages(result.log_messages, f'Job-{result.job_id}: ')  # will do nothing if log_messages is None or empty
            callback = self.callbacks.pop(result.job_id)
            callback(result)
