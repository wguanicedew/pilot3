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
# - Wen Guan, wen.guan@cern.ch, 2017
# - Paul Nilsson, paul.nilsson@cern.ch, 2021-23

import logging
import os
import threading
import time
import traceback

from pilot.common.exception import PilotException, MessageFailure


logger = logging.getLogger(__name__)


class MessageThread(threading.Thread):
    """
    A thread to receive messages from payload and put recevied messages to the out queues.
    """

    def __init__(self, message_queue, socket_name=None, context='local', **kwds):
        """
        Initialize yampl server socket.

        :param message_queue: a queue to transfer messages between current instance and ESProcess.
        :param socket_name: name of the socket between current process and payload.
        :param context: name of the context between current process and payload, default is 'local'.
        :param **kwds: other parameters.

        :raises MessageFailure: when failed to setup message socket.
        """

        threading.Thread.__init__(self, **kwds)
        self.setName("MessageThread")
        self.__message_queue = message_queue
        self._socket_name = socket_name
        self.__stop = threading.Event()

        logger.info('try to import yampl')
        try:
            import yampl
        except Exception as e:
            raise MessageFailure(f"Failed to import yampl: {e}")
        logger.info('finished to import yampl')

        logger.info('start to setup yampl server socket.')
        try:
            if self._socket_name is None or len(self._socket_name) == 0:
                self._socket_name = f'EventService_EventRanges_{os.getpid()}'
            self.__message_server = yampl.ServerSocket(self._socket_name, context)
        except Exception as exc:
            raise MessageFailure(f"failed to setup yampl server socket: {exc} {traceback.print_exc()}")
        logger.info(f'finished to setup yampl server socket(socket_name: {self._socket_name}, context:{context}).')

    def get_yampl_socket_name(self):
        return self._socket_name

    def send(self, message):
        """
        Send messages to payload through yampl server socket.

        :param message: String of the message.

        :raises MessageFailure: When failed to send a message to the payload.
        """
        logger.debug(f'Send a message to yampl: {message}')
        try:
            if not self.__message_server:
                raise MessageFailure("No message server.")
            self.__message_server.send_raw(message.encode('utf8'))  # Python 2 and 3
        except Exception as e:
            raise MessageFailure(e)

    def stop(self):
        """
        Set stop event.
        """
        logger.debug('set stop event')
        self.__stop.set()

    def is_stopped(self):
        """
        Get status whether stop event is set.

        :returns: True if stop event is set, otherwise False.
        """
        return self.__stop.is_set()

    def terminate(self):
        """
        Terminate message server.
        """
        if self.__message_server:
            logger.info("Terminating message server.")
            del self.__message_server
            self.__message_server = None

    def run(self):
        """
        Main thread loop to poll messages from payload and
        put received into message queue for other processes to fetch.
        """
        logger.info('Message thread starts to run.')
        try:
            while True:
                if self.is_stopped():
                    self.terminate()
                    break
                if not self.__message_server:
                    raise MessageFailure("No message server.")

                size, buf = self.__message_server.try_recv_raw()
                if size == -1:
                    time.sleep(0.01)
                else:
                    self.__message_queue.put(buf.decode('utf8'))  # Python 2 and 3
        except PilotException as exc:
            self.terminate()
            logger.error(f"Pilot Exception: Message thread got an exception, will finish: {exc.get_detail()}, {traceback.format_exc()}")
            # raise exc
        except Exception as exc:
            self.terminate()
            logger.error(f"Message thread got an exception, will finish: {exc}")
            # raise MessageFailure(exc)
        self.terminate()
        logger.info('Message thread finished.')
