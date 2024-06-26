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
# - Wen Guan, wen.guan@cern.ch, 2017-2018
# - Paul Nilsson, paul.nilsson@cern.ch, 2017-2024

"""Exceptions set by the pilot."""

import time
import threading
import traceback
from collections.abc import Callable
from sys import exc_info
from typing import Any

from .errorcodes import ErrorCodes

errors = ErrorCodes()


class PilotException(Exception):
    """Pilot exceptions class."""

    _error_code = None
    _message = None

    def __init__(self, *args, **kwargs):
        """Set default or initial values."""
        super().__init__(args, kwargs)
        self.args = args
        self.kwargs = kwargs
        code = self.kwargs.get("code", None)
        if code:
            self._error_code = code
        else:
            self._error_code = errors.UNKNOWNEXCEPTION
        self._message = errors.get_error_message(self._error_code)
        self._error_string = None
        self._stack_trace = f"{traceback.format_exc()}"

    def __str__(self):
        """Set and return the error string for string representation of the class instance."""
        try:
            self._error_string = (
                f"error code: {self._error_code}, message: {self._message % self.kwargs}"
            )
        except TypeError:
            # at least get the core message out if something happened
            self._error_string = (
                f"error code: {self._error_code}, message: {self._message}"
            )

        if len(self.args) > 0:
            # If there is a non-kwarg parameter, assume it's the error
            # message or reason description and tack it on to the end
            # of the exception message
            # Convert all arguments into their string representations...
            try:
                args = [f"{arg}" for arg in self.args if arg]
            except TypeError:
                args = [f"{self.args}"]
            self._error_string = self._error_string + "\ndetails: %s" % "\n".join(args)
        return self._error_string.strip()

    def get_detail(self):
        """Set and return the error string with the exception details."""
        try:
            self._error_string = (
                f"error code: {self._error_code}, message: {self._message % self.kwargs}"
            )
        except TypeError:
            # at least get the core message out if something happened
            self._error_string = (
                f"error code: {self._error_code}, message: {self._message}"
            )

        return self._error_string + f"\nstacktrace: {self._stack_trace}"

    def get_error_code(self):
        """Return the error code."""
        return self._error_code

    def get_last_error(self):
        """Return the last error message."""
        if self.args:
            return self.args[-1]
        return self._message


# class NotImplementedError(PilotException):
#    """
#    Not implemented exception.
#    """
#    def __init__(self, *args, **kwargs):
#        super().__init__(args, kwargs)
#        self._error_code = errors.NOTIMPLEMENTED
#        self._message = errors.get_error_message(self._error_code)


class UnknownException(PilotException):
    """Unknown exception."""

    def __init__(self, *args, **kwargs):
        """Set default and initial values."""
        super().__init__(args, kwargs)
        self._error_code = errors.UNKNOWNEXCEPTION
        self._message = errors.get_error_message(self._error_code)


class NoLocalSpace(PilotException):
    """Not enough local space."""

    def __init__(self, *args, **kwargs):
        """Set default and initial values."""
        super().__init__(args, kwargs)
        self._error_code = errors.NOLOCALSPACE
        self._message = errors.get_error_message(self._error_code)


class SizeTooLarge(PilotException):
    """Too large input files."""

    def __init__(self, *args, **kwargs):
        """Set default and initial values."""
        super().__init__(args, kwargs)
        self._error_code = errors.SIZETOOLARGE
        self._message = errors.get_error_message(self._error_code)


class StageInFailure(PilotException):
    """Failed to stage-in file."""

    def __init__(self, *args, **kwargs):
        """Set default and initial values."""
        super().__init__(args, kwargs)
        self._error_code = errors.STAGEINFAILED
        self._message = errors.get_error_message(self._error_code)


class StageOutFailure(PilotException):
    """Failed to stage-out file."""

    def __init__(self, *args, **kwargs):
        """Set default and initial values."""
        super().__init__(args, kwargs)
        self._error_code = errors.STAGEOUTFAILED
        self._message = errors.get_error_message(self._error_code)


class SetupFailure(PilotException):
    """Failed to setup environment."""

    def __init__(self, *args, **kwargs):
        """Set default and initial values."""
        super().__init__(args, kwargs)
        self._error_code = errors.SETUPFAILURE
        self._message = errors.get_error_message(self._error_code)


class RunPayloadFailure(PilotException):
    """Failed to execute payload."""

    def __init__(self, *args, **kwargs):
        """Set default and initial values."""
        super().__init__(args, kwargs)
        self._error_code = errors.PAYLOADEXECUTIONFAILURE
        self._message = errors.get_error_message(self._error_code)


class MessageFailure(PilotException):
    """Failed to handle messages."""

    def __init__(self, *args, **kwargs):
        """Set default and initial values."""
        super().__init__(args, kwargs)
        self._error_code = errors.MESSAGEHANDLINGFAILURE
        self._message = errors.get_error_message(self._error_code)


class CommunicationFailure(PilotException):
    """Failed to communicate with servers such as Panda, Harvester, ACT and so on."""

    def __init__(self, *args, **kwargs):
        """Set default and initial values."""
        super().__init__(args, kwargs)
        self._error_code = errors.COMMUNICATIONFAILURE
        self._message = errors.get_error_message(self._error_code)


class FileHandlingFailure(PilotException):
    """Failed during file handling."""

    def __init__(self, *args, **kwargs):
        """Set default and initial values."""
        super().__init__(args, kwargs)
        self._error_code = errors.FILEHANDLINGFAILURE
        self._message = errors.get_error_message(self._error_code)


class NoSuchFile(PilotException):
    """No such file or directory."""

    def __init__(self, *args, **kwargs):
        """Set default and initial values."""
        super().__init__(args, kwargs)
        self._error_code = errors.NOSUCHFILE
        self._message = errors.get_error_message(self._error_code)


class ConversionFailure(PilotException):
    """Failed to convert object data."""

    def __init__(self, *args, **kwargs):
        """Set default and initial values."""
        super().__init__(args, kwargs)
        self._error_code = errors.CONVERSIONFAILURE
        self._message = errors.get_error_message(self._error_code)


class MKDirFailure(PilotException):
    """Failed to create local directory."""

    def __init__(self, *args, **kwargs):
        """Set default and initial values."""
        super().__init__(args, kwargs)
        self._error_code = errors.MKDIR
        self._message = errors.get_error_message(self._error_code)


class NoGridProxy(PilotException):
    """Grid proxy not valid."""

    def __init__(self, *args, **kwargs):
        """Set default and initial values."""
        super().__init__(args, kwargs)
        self._error_code = errors.NOPROXY
        self._message = errors.get_error_message(self._error_code)


class NoVomsProxy(PilotException):
    """Voms proxy not valid."""

    def __init__(self, *args, **kwargs):
        """Set default and initial values."""
        super().__init__(args, kwargs)
        self._error_code = errors.NOVOMSPROXY
        self._message = errors.get_error_message(self._error_code)


class TrfDownloadFailure(PilotException):
    """Transform could not be downloaded."""

    def __init__(self, *args, **kwargs):
        """Set default and initial values."""
        super().__init__(args, kwargs)
        self._error_code = errors.TRFDOWNLOADFAILURE
        self._message = errors.get_error_message(self._error_code)


class NotDefined(PilotException):
    """Not defined exception."""

    def __init__(self, *args, **kwargs):
        """Set default and initial values."""
        super().__init__(args, kwargs)
        self._error_code = errors.NOTDEFINED
        self._message = errors.get_error_message(self._error_code)


class NotSameLength(PilotException):
    """Not same length exception."""

    def __init__(self, *args, **kwargs):
        """Set default and initial values."""
        super().__init__(args, kwargs)
        self._error_code = errors.NOTSAMELENGTH
        self._message = errors.get_error_message(self._error_code)


class ESRecoverable(PilotException):
    """Event service recoverable exception."""

    def __init__(self, *args, **kwargs):
        """Set default and initial values."""
        super().__init__(args, kwargs)
        self._error_code = errors.ESRECOVERABLE
        self._message = errors.get_error_message(self._error_code)


class ESFatal(PilotException):
    """Event service fatal exception."""

    def __init__(self, *args, **kwargs):
        """Set default and initial values."""
        super().__init__(args, kwargs)
        self._error_code = errors.ESFATAL
        self._message = errors.get_error_message(self._error_code)


class ExecutedCloneJob(PilotException):
    """Clone job executed exception."""

    def __init__(self, *args, **kwargs):
        """Set default and initial values."""
        super().__init__(args, kwargs)
        self._error_code = errors.EXECUTEDCLONEJOB
        self._message = errors.get_error_message(self._error_code)


class ESNoEvents(PilotException):
    """Event service no events exception."""

    def __init__(self, *args, **kwargs):
        """Set default and initial values."""
        super().__init__(args, kwargs)
        self._error_code = errors.ESNOEVENTS
        self._message = errors.get_error_message(self._error_code)


class ExceededMaxWaitTime(PilotException):
    """Exceeded maximum waiting time (after abort_job has been set)."""

    def __init__(self, *args, **kwargs):
        """Set default and initial values."""
        super().__init__(args, kwargs)
        self._error_code = errors.EXCEEDEDMAXWAITTIME
        self._message = errors.get_error_message(self._error_code)


class BadXML(PilotException):
    """Badly formed XML."""

    def __init__(self, *args, **kwargs):
        """Set default and initial values."""
        super().__init__(args, kwargs)
        self._error_code = errors.BADXML
        self._message = errors.get_error_message(self._error_code)


class NoSoftwareDir(PilotException):
    """Software applications directory does not exist."""

    def __init__(self, *args, **kwargs):
        """Set default and initial values."""
        super().__init__(args, kwargs)
        self._error_code = errors.NOSOFTWAREDIR
        self._message = errors.get_error_message(self._error_code)


class LogFileCreationFailure(PilotException):
    """Log file could not be created."""

    def __init__(self, *args, **kwargs):
        """Set default and initial values."""
        super().__init__(args, kwargs)
        self._error_code = errors.LOGFILECREATIONFAILURE
        self._message = errors.get_error_message(self._error_code)


class QueuedataFailure(PilotException):
    """Failed to download queuedata."""

    def __init__(self, *args, **kwargs):
        """Set default and initial values."""
        super().__init__(args, kwargs)
        self._error_code = errors.QUEUEDATA
        self._message = errors.get_error_message(self._error_code)


class QueuedataNotOK(PilotException):
    """Queuedata is corrupt."""

    def __init__(self, *args, **kwargs):
        """Set default and initial values."""
        super().__init__(args, kwargs)
        self._error_code = errors.QUEUEDATANOTOK
        self._message = errors.get_error_message(self._error_code)


class ReplicasNotFound(PilotException):
    """No matching replicas were found in list_replicas() output."""

    def __init__(self, *args, **kwargs):
        """Set default and initial values."""
        super().__init__(args, kwargs)
        self._error_code = errors.NOREPLICAS
        self._message = errors.get_error_message(self._error_code)


class MiddlewareImportFailure(PilotException):
    """No matching replicas were found in list_replicas() output."""

    def __init__(self, *args, **kwargs):
        """Set default and initial values."""
        super().__init__(args, kwargs)
        self._error_code = errors.MIDDLEWAREIMPORTFAILURE
        self._message = errors.get_error_message(self._error_code)


class JobAlreadyRunning(PilotException):
    """Clone job is already running elsewhere."""

    def __init__(self, *args, **kwargs):
        """Set default and initial values."""
        super().__init__(args, kwargs)
        self._error_code = errors.JOBALREADYRUNNING
        self._message = errors.get_error_message(self._error_code)

    def __str__(self):
        """Return string for exception object."""
        tmp = f" : {repr(self.args) if self.args else ''}"
        return f"{self.__class__.__name__}: {self._message}, {tmp}"


class ExcThread(threading.Thread):
    """Support class that allows for catching exceptions in threads."""

    def __init__(
        self, bucket: Any, target: Callable, kwargs: dict[str, Any], name: str
    ):
        """
        Set data members.

        Init function with a bucket that can be used to communicate exceptions to the caller.
        The bucket is a Queue.queue() or queue.Queue() object that can hold an exception thrown by a thread.

        :param bucket: queue based bucket (Any)
        :param target: target function to execute (Callable)
        :param kwargs: target function options (dict)
        :param name: name (str).
        """
        threading.Thread.__init__(self, target=target, kwargs=kwargs, name=name)
        self.name = name
        self.bucket = bucket
        self._target = target
        self._kwargs = kwargs

    def run(self):
        """
        Thread run function.

        Any exceptions in the threads are caught in this function and placed in the bucket of the current thread.
        The bucket will be emptied by the control module that launched the thread. E.g. an exception is thrown in
        the retrieve thread (in function retrieve()) that is created by the job.control thread. The exception is caught
        by the run() function and placed in the bucket belonging to the retrieve thread. The bucket is emptied in
        job.control().
        """
        # pylint: disable=broad-except
        try:
            self._target(**self.kwargs)
        except ValueError:
            print(f"ValueError caught by thread run() function: {exc_info()}")
            print(traceback.format_exc())
            print(traceback.print_tb(exc_info()[2]))
            self.bucket.put(exc_info())
            print(
                f"exception has been put in bucket queue belonging to thread '{self.name}'"
            )
            args = self._kwargs.get("args", None)
            if args:
                print(
                    "setting graceful stop in 10 s since there is no point in continuing"
                )
                time.sleep(10)
                args.graceful_stop.set()
        except Exception:
            # logger object can't be used here for some reason:
            # IOError: [Errno 2] No such file or directory: '/state/partition1/scratch/PanDA_Pilot2_*/pilotlog.txt'
            print(f"unexpected exception caught by thread run() function: {exc_info()}")
            print(traceback.format_exc())
            print(traceback.print_tb(exc_info()[2]))
            self.bucket.put(exc_info())
            print(
                f"exception has been put in bucket queue belonging to thread '{self.name}'"
            )
            args = self._kwargs.get("args", None)
            if args:
                # the sleep is needed to allow the threads to catch up
                print(
                    "setting graceful stop in 10 s since there is no point in continuing"
                )
                time.sleep(10)
                args.graceful_stop.set()

    @property
    def kwargs(self) -> dict[str, Any]:
        """Help Pyright understand the type for self._kwargs."""
        return self._kwargs

    def get_bucket(self):
        """
        Return the bucket object that holds any information about thrown exceptions.

        :return: bucket (Queue object)
        """
        return self.bucket
