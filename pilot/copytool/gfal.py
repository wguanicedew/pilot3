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
# - Pavlo Svirin, pavlo.svirin@cern.ch, 2017
# - Tobias Wegner, tobias.wegner@cern.ch, 2018
# - Paul Nilsson, paul.nilsson@cern.ch, 2018-2024
# - Alexey Anisenkov, anisyonk@cern.ch, 2018

"""GFAL2 copy tool."""

import errno
import logging
import os
from time import time

from pilot.common.exception import (
    PilotException,
    ErrorCodes,
    StageInFailure,
    StageOutFailure
)
from pilot.util.container import execute
#from pilot.util.timer import timeout
from .common import (
    resolve_common_transfer_errors,
    get_timeout
)

logger = logging.getLogger(__name__)

require_replicas = True  ## indicate if given copytool requires input replicas to be resolved

allowed_schemas = ['srm', 'gsiftp', 'https', 'davs', 'root']  # prioritized list of supported schemas for transfers by given copytool


def is_valid_for_copy_in(files: list) -> bool:
    """
    Determine if this copytool is valid for input for the given file list.

    Placeholder.

    :param files: list of FileSpec objects (list).
    :return: always True (for now) (bool).
    """
    #for f in files:
    #    if not all(key in f for key in ('name', 'source', 'destination')):
    #        return False
    return True  ## FIX ME LATER


def is_valid_for_copy_out(files: list) -> bool:
    """
    Determine if this copytool is valid for output for the given file list.

    Placeholder.

    :param files: list of FileSpec objects (list).
    :return: always True (for now) (bool).
    """
    # for f in files:
    #    if not all(key in f for key in ('name', 'source', 'destination')):
    #        return False
    return True  ## FIX ME LATER


def copy_in(files: list, **kwargs: dict) -> list:
    """
    Download given files using gfal-copy command.

    :param files: list of `FileSpec` objects (list)
    :param kwargs: kwargs dictionary (dict)
    :raises: PilotException in case of controlled error
    :return: updated files (list).
    """
    #allow_direct_access = kwargs.get('allow_direct_access') or False
    trace_report = kwargs.get('trace_report')

    if not check_for_gfal():
        raise StageInFailure("No GFAL2 tools found")

    # note, env vars might be unknown inside middleware contrainers, if so get the value already in the trace report
    localsite = os.environ.get('RUCIO_LOCAL_SITE_ID', trace_report.get_value('localSite'))
    for fspec in files:
        # update the trace report
        localsite = localsite if localsite else fspec.ddmendpoint
        trace_report.update(localSite=localsite, remoteSite=fspec.ddmendpoint, filesize=fspec.filesize)
        trace_report.update(filename=fspec.lfn, guid=fspec.guid.replace('-', ''))
        trace_report.update(scope=fspec.scope, dataset=fspec.dataset)

        # continue loop for files that are to be accessed directly   ## TO BE DEPRECATED (should be applied at top level) (anisyonk)
        #if fspec.is_directaccess(ensure_replica=False) and allow_direct_access and fspec.accessmode == 'direct':
        #    fspec.status_code = 0
        #    fspec.status = 'remote_io'
        #    trace_report.update(url=fspec.turl, clientState='FOUND_ROOT', stateReason='direct_access')
        #    trace_report.send()
        #    continue

        trace_report.update(catStart=time())

        dst = fspec.workdir or kwargs.get('workdir') or '.'

        timeout = get_timeout(fspec.filesize)
        source = fspec.turl
        destination = f"file://{os.path.abspath(os.path.join(dst, fspec.lfn))}"

        cmd = ['gfal-copy --verbose -f', f' -t {timeout}']

        if fspec.checksum:
            cmd += ['-K', '%s:%s' % list(fspec.checksum.items())[0]]

        cmd += [source, destination]

        rcode, stdout, stderr = execute(" ".join(cmd), **kwargs)

        if rcode:  ## error occurred
            if rcode in [errno.ETIMEDOUT, errno.ETIME]:
                error = {'rcode': ErrorCodes.STAGEINTIMEOUT,
                         'state': 'CP_TIMEOUT',
                         'error': f'Copy command timed out: {stderr}'}
            else:
                error = resolve_common_transfer_errors(stdout + stderr, is_stagein=True)
            fspec.status = 'failed'
            fspec.status_code = error.get('rcode')
            trace_report.update(clientState=error.get('state') or 'STAGEIN_ATTEMPT_FAILED',
                                stateReason=error.get('error'), timeEnd=time())
            trace_report.send()

            raise PilotException(error.get('error'), code=error.get('rcode'), state=error.get('state'))

        fspec.status_code = 0
        fspec.status = 'transferred'
        trace_report.update(clientState='DONE', stateReason='OK', timeEnd=time())
        trace_report.send()

    return files


def copy_out(files: list, **kwargs: dict) -> list:
    """
    Upload given files using gfal command.

    :param files: Files to upload (files)
    :param kwargs: kwargs dictionary (dict)
    :return: updated files (list)
    :raises: PilotException in case of errors.
    """
    if not check_for_gfal():
        raise StageOutFailure("No GFAL2 tools found")

    trace_report = kwargs.get('trace_report')

    for fspec in files:
        trace_report.update(scope=fspec.scope, dataset=fspec.dataset, url=fspec.surl, filesize=fspec.filesize)
        trace_report.update(catStart=time(), filename=fspec.lfn, guid=fspec.guid.replace('-', ''))

        src = fspec.workdir or kwargs.get('workdir') or '.'

        timeout = get_timeout(fspec.filesize)

        source = f"file://{os.path.abspath(fspec.surl or os.path.join(src, fspec.lfn))}"
        destination = fspec.turl

        cmd = ['gfal-copy --verbose -f', f' -t {timeout}']

        if fspec.checksum:
            cmd += ['-K', '%s:%s' % list(fspec.checksum.items())[0]]  # Python 2/3

        cmd += [source, destination]

        rcode, stdout, stderr = execute(" ".join(cmd), **kwargs)

        if rcode:  ## error occurred
            if rcode in [errno.ETIMEDOUT, errno.ETIME]:
                error = {'rcode': ErrorCodes.STAGEOUTTIMEOUT,
                         'state': 'CP_TIMEOUT',
                         'error': f'Copy command timed out: {stderr}'}
            else:
                error = resolve_common_transfer_errors(stdout + stderr, is_stagein=False)
            fspec.status = 'failed'
            fspec.status_code = error.get('rcode')
            trace_report.update(clientState=error.get('state', None) or 'STAGEOUT_ATTEMPT_FAILED',
                                stateReason=error.get('error', 'unknown error'),
                                timeEnd=time())
            trace_report.send()
            raise PilotException(error.get('error'), code=error.get('rcode'), state=error.get('state'))

        fspec.status_code = 0
        fspec.status = 'transferred'
        trace_report.update(clientState='DONE', stateReason='OK', timeEnd=time())
        trace_report.send()

    return files


def move_all_files_in(files: list, nretries: int = 1) -> (int, str, str):   ### NOT USED -- TO BE DEPRECATED
    """
    Move all input files.

    :param files: list of FileSpec objects (list)
    :param nretries: number of retries; sometimes there can be a timeout copying, but the next attempt may succeed (int)
    :return: exit_code (int), stdout (str), stderr (str).
    """
    exit_code = 0
    stdout = ""
    stderr = ""

    for entry in files:  # entry = {'name':<filename>, 'source':<dir>, 'destination':<dir>}
        logger.info(f"transferring file {entry['name']} from {entry['source']} to {entry['destination']}")

        source = entry['source'] + '/' + entry['name']
        # why /*4 ? Because sometimes gfal-copy complains about file:// protocol (anyone knows why?)
        # with four //// this does not seem to happen
        destination = 'file:///' + os.path.join(entry['destination'], entry['name'])
        for retry in range(nretries):
            exit_code, stdout, stderr = move(source, destination, entry.get('recursive', False))

            if exit_code != 0:
                if ((exit_code not in (errno.ETIMEDOUT, errno.ETIME)) or ((retry + 1) == nretries)):
                    logger.warning(f"transfer failed: exit code = {exit_code}, stdout = {stdout}, stderr = {stderr}")
                    return exit_code, stdout, stderr
            else:  # all successful
                break

    return exit_code, stdout, stderr


def move_all_files_out(files: list, nretries: int = 1) -> (int, str, str):  ### NOT USED -- TO BE DEPRECATED
    """
    Move all output files.

    :param files: list of FileSpec objects (list)
    :param nretries: number of retries; sometimes there can be a timeout copying, but the next attempt may succeed (int)
    :return: exit_code (int), stdout (str), stderr (str).
    """
    exit_code = 0
    stdout = ""
    stderr = ""

    for entry in files:  # entry = {'name':<filename>, 'source':<dir>, 'destination':<dir>}
        logger.info(f"transferring file {entry['name']} from {entry['source']} to {entry['destination']}")

        destination = entry['destination'] + '/' + entry['name']
        # why /*4 ? Because sometimes gfal-copy complains about file:// protocol (anyone knows why?)
        # with four //// this does not seem to happen
        source = 'file:///' + os.path.join(entry['source'], entry['name'])
        for retry in range(nretries):
            exit_code, stdout, stderr = move(source, destination)

            if exit_code != 0:
                if ((exit_code not in (errno.ETIMEDOUT, errno.ETIME)) or ((retry + 1) == nretries)):
                    logger.warning(f"transfer failed: exit code = {exit_code}, stdout = {stdout}, stderr = {stderr}")
                    return exit_code, stdout, stderr
            else:  # all successful
                break

    return exit_code, stdout, stderr


#@timeout(seconds=10800)
def move(source: str, destination: str, recursive: bool = False) -> (int, str, str):
    """
    Perform gfal-copy from the given source location to the given destination.

    :param source: file source path (str)
    :param destination: destination path (str)
    :param recursive: True if -r option is desired, False otherwise (bool)
    :return: exit code (int), stdout (str), stderr (str).
    """
    if recursive:
        cmd = f"gfal-copy -r {source} {destination}"
    else:
        cmd = f"gfal-copy {source} {destination}"
    print(cmd)
    exit_code, stdout, stderr = execute(cmd)

    return exit_code, stdout, stderr


def check_for_gfal():
    """
    Check if gfal-copy is locally available.

    :return: True if gfal-copy is available, False otherwise (bool).
    """
    exit_code, _, _ = execute('which gfal-copy')
    return exit_code == 0
