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
# - Paul Nilsson, paul.nilsson@cern.ch, 2021-2024

"""S3 copy tool."""

import logging
import os
from glob import glob
from typing import Any
from urllib.parse import urlparse

try:
    import boto3
    from botocore.exceptions import ClientError
except Exception:
    pass

from pilot.common.errorcodes import ErrorCodes
from pilot.common.exception import PilotException
from pilot.info import infosys
from pilot.util.config import config
from pilot.util.ruciopath import get_rucio_path
from .common import resolve_common_transfer_errors

logger = logging.getLogger(__name__)
errors = ErrorCodes()

require_replicas = False          # indicates if given copytool requires input replicas to be resolved
require_input_protocols = True    # indicates if given copytool requires input protocols and manual generation of input replicas
require_protocols = True          # indicates if given copytool requires protocols to be resolved first for stage-out

allowed_schemas = ['srm', 'gsiftp', 'https', 'davs', 'root', 's3', 's3+rucio']


def is_valid_for_copy_in(files: list) -> bool:
    """
    Determine if this copytool is valid for input for the given file list.

    Placeholder.

    :param files: list of FileSpec objects (list)
    :return: always True (for now) (bool).
    """
    if files:  # to get rid of pylint warning
        pass
    # for f in files:
    #    if not all(key in f for key in ('name', 'source', 'destination')):
    #        return False
    return True  ## FIX ME LATER


def is_valid_for_copy_out(files: list) -> bool:
    """
    Determine if this copytool is valid for output for the given file list.

    Placeholder.

    :param files: list of FileSpec objects (list)
    :return: always True (for now) (bool).
    """
    if files:  # to get rid of pylint warning
        pass
    # for f in files:
    #    if not all(key in f for key in ('name', 'source', 'destination')):
    #        return False
    return True  ## FIX ME LATER


def get_pilot_s3_profile() -> str:
    """
    Get the PANDA_PILOT_AWS_PROFILE environment variable.

    :return: PANDA_PILOT_AWS_PROFILE (str).
    """
    return os.environ.get("PANDA_PILOT_AWS_PROFILE", None)


def get_copy_out_extend() -> str:
    """
    Get the PANDA_PILOT_COPY_OUT_EXTEND environment variable.

    :return: PANDA_PILOT_COPY_OUT_EXTEND (str).
    """
    return os.environ.get("PANDA_PILOT_COPY_OUT_EXTEND", None)


def get_endpoint_bucket_key(surl: str) -> (str, str, str):
    """
    Get the endpoint, bucket and key from the given SURL.

    :param surl: SURL (str)
    :return: endpoint (str), bucket (str), key (str).
    """
    parsed = urlparse(surl)
    endpoint = parsed.scheme + '://' + parsed.netloc
    full_path = parsed.path
    while "//" in full_path:
        full_path = full_path.replace('//', '/')

    parts = full_path.split('/')
    bucket = parts[1]
    key = '/'.join(parts[2:])

    return endpoint, bucket, key


def resolve_surl(fspec: Any, protocol: dict, ddmconf: dict, **kwargs: dict) -> dict:
    """
    Get final destination SURL for file to be transferred to Objectstore.

    Can be customized at the level of specific copytool.

    :param fspec: FileSpec object (Any)
    :param protocol: suggested protocol (dict)
    :param ddmconf: full ddm storage data (dict)
    :param kwargs: kwargs dictionary (dict)
    :return: SURL dictionary {'surl': surl} (dict).
    """
    if kwargs:  # to get rid of pylint warning
        pass
    try:
        pandaqueue = infosys.pandaqueue
    except Exception:
        pandaqueue = ""
    if pandaqueue is None:
        pandaqueue = ""

    ddm = ddmconf.get(fspec.ddmendpoint)
    if not ddm:
        raise PilotException(f'failed to resolve ddmendpoint by name={fspec.ddmendpoint}')

    if ddm.is_deterministic:
        surl = protocol.get('endpoint', '') + os.path.join(protocol.get('path', ''), get_rucio_path(fspec.scope, fspec.lfn))
    elif ddm.type in {'OS_ES', 'OS_LOGS'}:
        try:
            pandaqueue = infosys.pandaqueue
        except AttributeError:
            pandaqueue = ""
        if pandaqueue is None:
            pandaqueue = ""

        dataset = fspec.dataset
        if dataset:
            dataset = dataset.replace("#{pandaid}", os.environ['PANDAID'])
        else:
            dataset = ""

        remote_path = os.path.join(protocol.get('path', ''), pandaqueue, dataset)
        surl = protocol.get('endpoint', '') + remote_path

        fspec.protocol_id = protocol.get('id')
    else:
        raise PilotException(f'resolve_surl(): Failed to construct SURL for non deterministic ddm={fspec.ddmendpoint}: NOT IMPLEMENTED')

    logger.info(f'resolve_surl, surl: {surl}')
    # example:
    #   protocol = {u'path': u'/atlas-eventservice', u'endpoint': u's3://s3.cern.ch:443/', u'flavour': u'AWS-S3-SSL', u'id': 175}
    #   surl = 's3://s3.cern.ch:443//atlas-eventservice/EventService_premerge_24706191-5013009653-24039149400-322-5.tar'
    return {'surl': surl}


def copy_in(files: list, **kwargs: dict) -> list:
    """
    Download given files from an S3 bucket.

    :param files: list of `FileSpec` objects (list)
    :param kwargs: kwargs dictionary (dict)
    :raises: PilotException in case of controlled error
    :return: updated list of files (list).
    """
    for fspec in files:

        dst = fspec.workdir or kwargs.get('workdir') or '.'

        # bucket = 'bucket'  # UPDATE ME
        path = os.path.join(dst, fspec.lfn)
        logger.info(f'downloading surl {fspec.surl} to local file {path}')
        status, diagnostics = download_file(path, fspec.surl)

        if not status:  # an error occurred
            error = resolve_common_transfer_errors(diagnostics, is_stagein=True)
            fspec.status = 'failed'
            fspec.status_code = error.get('rcode')
            raise PilotException(error.get('error'), code=error.get('rcode'), state=error.get('state'))

        fspec.status_code = 0
        fspec.status = 'transferred'

    return files


def download_file(path: str, surl: str, object_name: str = None) -> (bool, str):
    """
    Download a file from an S3 bucket.

    :param path: path to local file after download (str)
    :param surl: source url to download from (str)
    :param object_name: S3 object name. If not specified then file_name from path is used (str)
    :return: True if file was uploaded - otherwise False (bool), diagnostics (str).
    """
    try:
        endpoint, bucket, object_name = get_endpoint_bucket_key(surl)
        session = boto3.Session(profile_name=get_pilot_s3_profile())
        # s3 = boto3.client('s3')
        s3 = session.client('s3', endpoint_url=endpoint)
        s3.download_file(bucket, object_name, path)
    except ClientError as error:
        diagnostics = f'S3 ClientError: {error}'
        logger.critical(diagnostics)
        return False, diagnostics
    except Exception as error:
        diagnostics = f'exception caught in s3_client: {error}'
        logger.critical(diagnostics)
        return False, diagnostics

    return True, ""


def copy_out_extend(files: list, **kwargs: dict) -> list:
    """
    Upload given files to S3 storage.

    :param files: list of `FileSpec` objects (list)
    :param kwargs: kwargs dictionary (dict)
    :raises: PilotException in case of controlled error
    :return: updated list of files (list).
    """
    workdir = kwargs.pop('workdir')

    for fspec in files:

        # path = os.path.join(workdir, fspec.lfn)
        logger.info(f'uploading {workdir} to {fspec.turl}')

        logfiles = []
        lfn = fspec.lfn.strip()
        if lfn == '/' or lfn.endswith("log.tgz"):
            # ["pilotlog.txt", "payload.stdout", "payload.stderr"]:
            logfiles += glob(workdir + '/payload*.*')
            logfiles += glob(workdir + '/memory_monitor*.*')
            # if lfn.find('/') < 0:
            #     lfn_path = os.path.join(workdir, lfn)
            #    if os.path.exists(lfn_path) and lfn_path not in logfiles:
            #        logfiles += [lfn_path]
            logfiles += glob(workdir + '/pilotlog*.*')
        else:
            logfiles = [os.path.join(workdir, lfn)]

        for path in logfiles:
            logfile = os.path.basename(path)
            if os.path.exists(path):
                full_url = os.path.join(fspec.turl, logfile)
                logger.info(f'uploading {path} to {full_url}')
                status, diagnostics = upload_file(path, full_url)

                if not status:  # an error occurred
                    # create new error code(s) in ErrorCodes.py and set it/them in resolve_common_transfer_errors()
                    error = resolve_common_transfer_errors(diagnostics, is_stagein=False)
                    fspec.status = 'failed'
                    fspec.status_code = error.get('rcode')
                    raise PilotException(error.get('error'), code=error.get('rcode'), state=error.get('state'))
            else:
                diagnostics = f'local output file does not exist: {path}'
                logger.warning(diagnostics)
                fspec.status = 'failed'
                fspec.status_code = errors.STAGEOUTFAILED
                # raise PilotException(diagnostics, code=fspec.status_code, state=fspec.status)

        if fspec.status is None:
            fspec.status = 'transferred'
            fspec.status_code = 0

    return files


def copy_out(files: list, **kwargs: dict) -> list:
    """
    Upload given files to S3 storage.

    :param files: list of `FileSpec` objects (list)
    :param kwargs: kwargs dictionary (dict)
    :raise: PilotException in case of controlled error
    :return: updated list of files (list).
    """
    if get_copy_out_extend():
        return copy_out_extend(files, **kwargs)

    workdir = kwargs.pop('workdir')

    for fspec in files:

        path = os.path.join(workdir, fspec.lfn)
        if os.path.exists(path):
            # bucket = 'bucket'  # UPDATE ME
            logger.info(f'uploading {path} to {fspec.turl}')
            full_url = os.path.join(fspec.turl, fspec.lfn)
            status, diagnostics = upload_file(path, full_url)

            if not status:  # an error occurred
                # create new error code(s) in ErrorCodes.py and set it/them in resolve_common_transfer_errors()
                error = resolve_common_transfer_errors(diagnostics, is_stagein=False)
                fspec.status = 'failed'
                fspec.status_code = error.get('rcode')
                raise PilotException(error.get('error'), code=error.get('rcode'), state=error.get('state'))
        else:
            diagnostics = f'local output file does not exist: {path}'
            logger.warning(diagnostics)
            fspec.status = 'failed'
            fspec.status_code = errors.STAGEOUTFAILED
            raise PilotException(diagnostics, code=fspec.status_code, state=fspec.status)

        fspec.status = 'transferred'
        fspec.status_code = 0

    return files


def upload_file(file_name: str, full_url: str) -> (bool, str):
    """
    Upload a file to an S3 bucket.

    :param file_name: file to upload (str)
    :param full_url: full URL to upload to (str)
    :return: True if file was uploaded - otherwise False (bool), diagnostics (str).
    """
    # upload the file
    try:
        # s3_client = boto3.client('s3')
        endpoint, bucket, object_name = get_endpoint_bucket_key(full_url)
        session = boto3.Session(profile_name=get_pilot_s3_profile())
        s3_client = session.client('s3', endpoint_url=endpoint)
        # response = s3_client.upload_file(file_name, bucket, object_name)
        s3_client.upload_file(file_name, bucket, object_name)
        if object_name.endswith(config.Pilot.pilotlog):
            os.environ['GTAG'] = full_url
            logger.debug(f"Set envvar GTAG with the pilotLot URL={full_url}")
    except ClientError as error:
        diagnostics = f'S3 ClientError: {error}'
        logger.critical(diagnostics)
        return False, diagnostics
    except Exception as error:
        diagnostics = f'exception caught in s3_client: {error}'
        logger.critical(diagnostics)
        return False, diagnostics

    return True, ""
