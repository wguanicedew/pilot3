#!/usr/bin/env python
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
#
# Authors:
# - Paul Nilsson, paul.nilsson@cern.ch, 2019-24

import functools
import logging
import signal
import threading
import traceback
import queue

from collections import namedtuple
from os import getpid
from shutil import rmtree
from sys import stderr
from time import time
from types import FrameType

from pilot.common.exception import ExcThread
from pilot.control import (
    data,
    job,
    monitor
)
from pilot.util.constants import (
    MAX_KILL_WAIT_TIME,
    SUCCESS,
    PILOT_KILL_SIGNAL,
)
from pilot.util.processes import (
    kill_processes,
    threads_aborted
)
from pilot.util.timing import add_to_pilot_timing

logger = logging.getLogger(__name__)
# Define Traces namedtuple at the module level
Traces = namedtuple("Traces", ["pilot"])


def interrupt(args: object, signum: int, frame: FrameType):
    """
    Interrupt function on the receiving end of kill signals.
    This function is forwarded any incoming signals (SIGINT, SIGTERM, etc) and will set abort_job which instructs
    the threads to abort the job.

    :param args: pilot arguments (object)
    :param signum: signal number (int)
    :param frame: stack/execution frame pointing to the frame that was interrupted by the signal (FrameType).
    """
    sig = [v for v, k in list(signal.__dict__.items()) if k == signum][0]
    args.signal_counter += 1

    # keep track of when first kill signal arrived, any stuck loops should abort at a defined cut off time
    if args.kill_time == 0:
        args.kill_time = int(time())

    max_kill_wait_time = MAX_KILL_WAIT_TIME + 60  # add another minute of grace to let threads finish
    current_time = int(time())
    if args.kill_time and current_time - args.kill_time > max_kill_wait_time:
        logger.warning('passed maximum waiting time after first kill signal - will commit suicide - farewell')
        try:
            if hasattr(args, 'sourcedir'):
                rmtree(args.sourcedir)
        except (TypeError, OSError) as e:
            logger.warning(e)

        logging.shutdown()
        kill_processes(getpid())

    add_to_pilot_timing('0', PILOT_KILL_SIGNAL, time(), args)
    add_to_pilot_timing('1', PILOT_KILL_SIGNAL, time(), args)
    logger.warning('caught signal: %s in FRAME=\n%s', sig, '\n'.join(traceback.format_stack(frame)))

    args.signal = sig
    logger.warning('will instruct threads to abort and update the server')
    args.abort_job.set()
    logger.warning('setting graceful stop (in case it was not set already)')
    args.graceful_stop.set()
    logger.warning('waiting for threads to finish')
    args.job_aborted.wait()


def run(args: object) -> Traces or None:
    """
    Main execution function for the stage-in workflow.

    The function sets up the internal queues which handle the flow of jobs.

    :param args: pilot arguments object (object)
    :return: traces object (Traces namedtuple or None).
    """
    logger.info('setting up signal handling')

    signal.signal(signal.SIGINT, functools.partial(interrupt, args))
    signal.signal(signal.SIGTERM, functools.partial(interrupt, args))
    signal.signal(signal.SIGQUIT, functools.partial(interrupt, args))
    signal.signal(signal.SIGSEGV, functools.partial(interrupt, args))
    signal.signal(signal.SIGXCPU, functools.partial(interrupt, args))
    signal.signal(signal.SIGUSR1, functools.partial(interrupt, args))
    signal.signal(signal.SIGBUS, functools.partial(interrupt, args))

    logger.info('setting up queues')
    queues = namedtuple('queues', ['jobs', 'data_in', 'data_out', 'current_data_in', 'validated_jobs', 'monitored_payloads',
                                   'finished_jobs', 'finished_data_in', 'finished_data_out', 'completed_jobids',
                                   'failed_jobs', 'failed_data_in', 'failed_data_out', 'completed_jobs'])

    queues.jobs = queue.Queue()
    queues.data_in = queue.Queue()
    queues.data_out = queue.Queue()

    queues.current_data_in = queue.Queue()
    queues.validated_jobs = queue.Queue()
    queues.monitored_payloads = queue.Queue()

    queues.finished_jobs = queue.Queue()
    queues.finished_data_in = queue.Queue()
    queues.finished_data_out = queue.Queue()

    queues.failed_jobs = queue.Queue()
    queues.failed_data_in = queue.Queue()
    queues.failed_data_out = queue.Queue()

    queues.completed_jobs = queue.Queue()
    queues.completed_jobids = queue.Queue()

    logger.info('setting up tracing')
    # Initialize traces with default values
    traces = Traces(pilot={"state": SUCCESS, "nr_jobs": 0, "error_code": 0, "command": None})

    # define the threads
    targets = {'job': job.control, 'data': data.control, 'monitor': monitor.control}
    threads = [ExcThread(bucket=queue.Queue(), target=target, kwargs={'queues': queues, 'traces': traces, 'args': args},
                         name=name) for name, target in list(targets.items())]

    logger.info('starting threads')
    _ = [thread.start() for thread in threads]

    logger.info('waiting for interrupts')

    thread_count = threading.active_count()
    try:
        while threading.active_count() > 1:
            for thread in threads:
                bucket = thread.get_bucket()
                try:
                    exc = bucket.get(block=False)
                except queue.Empty:
                    pass
                else:
                    _, exc_obj, _ = exc
                    # deal with the exception
                    print(f'received exception from bucket queue in generic workflow: {exc_obj}', file=stderr)

                thread.join(0.1)

            abort = False
            if thread_count != threading.active_count():
                # has all threads finished?
                #abort = threads_aborted(abort_at=1)
                abort = threads_aborted(caller='run')
                if abort:
                    break
    except Exception as exc:
        logger.warning(f"exception caught while handling threads: {exc}")
    finally:
        logger.info('all stager threads have been joined')

    logger.info(f"end of stager workflow (traces error code: {traces.pilot['error_code']})")

    return traces
