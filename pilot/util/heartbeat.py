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
# - Paul Nilsson, paul.nilsson@cern.ch, 2023

"""Functions related to heartbeat messages. It is especually needed for the pilot to know if it has been suspended."""

import logging
import os
import threading
import time

# from pilot.common.errorcodes import ErrorCodes
from pilot.common.exception import (
    PilotException,
    FileHandlingFailure,
    ConversionFailure
)
from pilot.util.config import config
from pilot.util.filehandling import (
    read_json,
    write_json
)

lock = threading.Lock()
logger = logging.getLogger(__name__)
# errors = ErrorCodes()


def update_pilot_heartbeat(update_time: int, name: str = 'pilot') -> bool:
    """
    Update the pilot heartbeat file.

    Dictionary = {last_pilot_heartbeat: <int>, last_server_update: <int>, ( last_looping_check: {job_id: <int>: <int>}, .. ) }
    (optionally add looping job info later).

    :param update_time: time of last update (int)
    :param name: name of the heartbeat to update, 'pilot' or 'server' (str)
    :return: True if successfully updated heartbeat file, False otherwise (bool).
    """
    filename = config.Pilot.pilot_heartbeat_file
    dictionary = read_pilot_heartbeat()
    if not dictionary:  # redundancy
        dictionary = {}

    with lock:
        dictionary[f'last_{name}_update'] = update_time
        status = write_json(filename, dictionary)
        if not status:
            logger.warning(f'failed to update heartbeat file: {filename}')
            return False

    return True


def read_pilot_heartbeat() -> dict:
    """
    Read the pilot heartbeat file.

    :return: dictionary with pilot heartbeat info (dict).
    """
    filename = config.Pilot.pilot_heartbeat_file
    dictionary = {}

    with lock:
        if os.path.exists(filename):
            try:
                dictionary = read_json(filename)
            except (PilotException, FileHandlingFailure, ConversionFailure) as exc:
                logger.warning(f'failed to read heartbeat file: {exc}')

    return dictionary


def get_last_update(name: str = 'pilot') -> int:
    """
    Return the time of the last pilot or server update.

    :param name: name of the heartbeat to return (str)
    :return: time of last pilot or server update (int).
    """
    dictionary = read_pilot_heartbeat()
    if dictionary:
        return dictionary.get(f'last_{name}_update', 0)

    return 0


def is_suspended(limit: int = 10 * 60) -> bool:
    """
    Check if the pilot was suspended.

    :param limit: time limit in seconds (int)
    :return: True if the pilot is suspended, False otherwise (bool).
    """
    dictionary = read_pilot_heartbeat()
    if dictionary:
        last_pilot_update = dictionary.get('last_pilot_update', 0)
        if last_pilot_update:
            # check if more than ten minutes has passed
            if time.time() - last_pilot_update > limit:
                return True

    return False
