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
# - Alexey Anisenkov, anisyonk@cern.ch, 2018
# - Paul Nilsson, paul.nilsson@cern.ch, 2019-24

"""
The implementation of data structure to host storage data description.

The main reasons for such incapsulation are to
 - apply in one place all data validation actions (for attributes and values)
 - introduce internal information schema (names of attribues) to remove direct dependency
 with data structrure, formats, names from external sources (e.g. AGIS/CRIC)

:author: Alexey Anisenkov
:contact: anisyonk@cern.ch
:date: January 2018
"""
import logging
import traceback
from os import environ
from typing import Any

from pilot.util import https
from pilot.util.config import config
from .basedata import BaseData

logger = logging.getLogger(__name__)


class StorageData(BaseData):
    """
    High-level object to host Storage details (available protocols, etc.)
    """

    ## put explicit list of all the attributes with comments for better inline-documentation by sphinx
    ## FIX ME LATER: use proper doc format

    ## incomplete list of attributes .. to be extended once becomes used

    pk = 0        # unique identification number
    name = ""     # DDMEndpoint name
    type = ""     # type of Storage <- can this be renamed to storagetype without causing any problem with queuedata?
    token = ""    # space token descriptor

    is_deterministic = None

    state = None
    site = None   # ATLAS Site name

    arprotocols = {}
    rprotocols = {}
    special_setup = {}
    resource = None

    # specify the type of attributes for proper data validation and casting
    _keys = {int: ['pk'],
             str: ['name', 'state', 'site', 'type', 'token'],
             dict: ['copytools', 'acopytools', 'astorages', 'arprotocols', 'rprotocols', 'resource'],
             bool: ['is_deterministic']
             }

    def __init__(self, data: dict):
        """
        Initialize StorageData object with input data.

        :param data: input dictionary of storage description by DDMEndpoint name as key (dict).
        """
        self.load(data)

        # DEBUG
        # import pprint
        # logger.debug(f'initialize StorageData from raw:\n{pprint.pformat(data)}')
        # logger.debug(f'final parsed StorageData content:\n{self}')

    def load(self, data: dict):
        """
        Construct and initialize data from ext source.

        :param data: input dictionary of storage description by DDMEndpoint name as key (dict).
        """
        # the translation map of the queue data attributes from external data to internal schema
        # first defined ext field name will be used
        # if key is not explicitly specified then ext name will be used as is
        ## fix me later to proper internal names if need

        kmap = {
            # 'internal_name': ('ext_name1', 'extname2_if_any')
            # 'internal_name2': 'ext_name3'
            'pk': 'id',
        }

        self._load_data(data, kmap)

    ## custom function pattern to apply extra validation to the key values
    ##def clean__keyname(self, raw, value):
    ##  :param raw: raw value passed from ext source as input
    ##  :param value: preliminary cleaned and casted to proper type value
    ##
    ##    return value

    # to be improved: move it to some data loader
    def get_security_key(self, secret_key: str, access_key: str) -> dict:
        """
        Get security key pair from panda.

        :param secret_key: secret key name (str)
        :param access_key: access key name (str)
        :return: dictionary with public and private keys (dict).
        """
        try:
            data = {'privateKeyName': secret_key, 'publicKeyName': access_key}
            url = environ.get('PANDA_SERVER_URL', config.Pilot.pandaserver)
            logger.info(f"requesting key pair from {url}: {data}")
            res = https.request(f'{url}/server/panda/getKeyPair', data=data)
            if res and res['StatusCode'] == 0:
                return {"publicKey": res["publicKey"], "privateKey": res["privateKey"]}
            logger.info(f"key pair returned wrong value: {res}")
        except Exception as exc:
            logger.error(f"failed to get key pair ({access_key},{secret_key}): {exc}, {traceback.format_exc()}")
        return {}

    def get_special_setup(self, protocol_id: Any = None):
        """
        Construct special setup for ddms such as objectstores.

        :param protocol_id: protocol id (Any)
        :return: special setup string (str).
        """
        logger.debug(f"get special setup for protocol id ({protocol_id})")
        if protocol_id in self.special_setup and self.special_setup[protocol_id]:
            return self.special_setup[protocol_id]

        if protocol_id is None or str(protocol_id) not in self.rprotocols:
            return None

        if self.type in {'OS_ES', 'OS_LOGS'}:
            self.special_setup[protocol_id] = None

            settings = self.rprotocols.get(str(protocol_id), {}).get('settings', {})
            access_key = settings.get('access_key', None)
            secret_key = settings.get('secret_key', None)
            is_secure = settings.get('is_secure', None)

            # make sure all things are correctly defined in AGIS.
            # If one of them is not defined correctly, will not setup this part. Then rucio client can try to use signed url.
            # This part is preferred because signed url is not efficient.
            if access_key and secret_key and is_secure:
                key_pair = self.get_security_key(secret_key, access_key)
                if "privateKey" not in key_pair or key_pair["privateKey"] is None:
                    logger.error("failed to get the key pair for S3 objectstore from panda")
                else:
                    self.special_setup[protocol_id] = f"export S3_ACCESS_KEY={key_pair['publicKey']}; " \
                                                      f"export S3_SECRET_KEY={key_pair['privateKey']}; " \
                                                      f"export S3_IS_SECURE={is_secure};"
                    logger.info(f"return key pair with public key: {key_pair['publicKey']}")
                    return self.special_setup[protocol_id]
        return None
