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
# - Paul Nilsson, paul.nilsson@cern.ch, 2018-24

import os
import logging
from xml.dom import minidom
from xml.etree import ElementTree

from pilot.util.filehandling import write_file

logger = logging.getLogger(__name__)


def create_input_file_metadata(file_dictionary: dict, workdir: str, filename: str = "PoolFileCatalog.xml") -> str:
    """
    Create a Pool File Catalog for the files listed in the input dictionary.

    The function creates properly formatted XML (pretty printed) and writes the XML to file.
    Note: any environment variables in the pfn tags will be expanded (see pilot/control/data::get_input_file_dictionary()).

    Format:
    dictionary = {'guid': 'pfn', ..}
    ->
    <POOLFILECATALOG>
    <!DOCTYPE POOLFILECATALOG SYSTEM "InMemory">
    <File ID="guid">
      <physical>
        <pfn filetype="ROOT_All" name="surl"/>
      </physical>
      <logical/>
    </File>
    <POOLFILECATALOG>

    :param file_dictionary: file dictionary (dict)
    :param workdir: job work directory (str)
    :param filename: PFC file name (str)
    :return: xml (str).
    """
    # create the file structure
    data = ElementTree.Element('POOLFILECATALOG')

    for fileid in list(file_dictionary.keys()):  # Python 2/3
        _file = ElementTree.SubElement(data, 'File')
        _file.set('ID', fileid)
        _physical = ElementTree.SubElement(_file, 'physical')
        _pfn = ElementTree.SubElement(_physical, 'pfn')
        _pfn.set('filetype', 'ROOT_All')
        _pfn.set('name', file_dictionary.get(fileid))
        ElementTree.SubElement(_file, 'logical')

    # create a new XML file with the results
    xml = ElementTree.tostring(data, encoding='utf8')
    xml = minidom.parseString(xml).toprettyxml(indent="  ")

    # stitch in the DOCTYPE
    xml = xml.replace('<POOLFILECATALOG>', '<!DOCTYPE POOLFILECATALOG SYSTEM "InMemory">\n<POOLFILECATALOG>')

    write_file(os.path.join(workdir, filename), xml, mute=False)

    return xml


def get_file_info_from_xml(workdir: str, filename: str = "PoolFileCatalog.xml") -> dict:
    """
    Return a file info dictionary based on the metadata in the given XML file.

    The file info dictionary is used to replace the input file LFN list in the job parameters with the full PFNs
    which are needed for direct access in production jobs.

    Example of PoolFileCatalog.xml:

    <?xml version="1.0" ?>
    <POOLFILECATALOG>
      <File ID="4ACC5018-2EA3-B441-BC11-0C0992847FD1">
        <physical>
          <pfn filetype="ROOT_ALL" name="root://dcgftp.usatlas.bnl.gov:1096//../AOD.11164242._001522.pool.root.1"/>
        </physical>
        <logical/>
      </File>
    </POOLFILECATALOG>

    which gives the following dictionary:

    {'AOD.11164242._001522.pool.root.1': ['root://dcgftp.usatlas.bnl.gov:1096//../AOD.11164242._001522.pool.root.1',
    '4ACC5018-2EA3-B441-BC11-0C0992847FD1']}

    :param workdir: directory of PoolFileCatalog.xml (str)
    :param filename: file name (default: PoolFileCatalog.xml) (str)
    :return: dictionary { LFN: [PFN, GUID], .. } (dict).
    """
    file_info_dictionary = {}
    tree = ElementTree.parse(os.path.join(workdir, filename))
    root = tree.getroot()
    # root.tag = POOLFILECATALOG

    for child in root:
        # child.tag = 'File', child.attrib = {'ID': '4ACC5018-2EA3-B441-BC11-0C0992847FD1'}
        guid = child.attrib['ID']
        for grandchild in child:
            # grandchild.tag = 'physical', grandchild.attrib = {}
            for greatgrandchild in grandchild:
                # greatgrandchild.tag = 'pfn', greatgrandchild.attrib = {'filetype': 'ROOT_ALL', 'name': 'root://dcgftp.usatlas.bnl ..'}
                pfn = greatgrandchild.attrib['name']
                lfn = os.path.basename(pfn)
                file_info_dictionary[lfn] = [pfn, guid]

    return file_info_dictionary


def get_metadata_from_xml(workdir: str, filename: str = "metadata.xml") -> dict:
    """
    Parse the payload metadata.xml file.

    Example of metadata.xml:

    <?xml version="1.0" encoding="UTF-8"?>
    <!DOCTYPE POOLFILECATALOG SYSTEM 'InMemory'>
    <POOLFILECATALOG>
      <File ID="D2A6D6F4-ADB2-B140-9C2E-D2D5C099B342">
        <logical>
          <lfn name="RDO_011a43ba-7c98-488d-8741-08da579c5de7.root"/>
        </logical>
        <metadata att_name="geometryVersion" att_value="ATLAS-R2-2015-03-01-00"/>
        <metadata att_name="conditionsTag" att_value="OFLCOND-RUN12-SDR-19"/>
        <metadata att_name="size" att_value="3250143"/>
        <metadata att_name="events" att_value="3"/>
        <metadata att_name="beamType" att_value="collisions"/>
        <metadata att_name="fileType" att_value="RDO"/>
      </File>
    </POOLFILECATALOG>

    which gives the following dictionary:

    {'RDO_011a43ba-7c98-488d-8741-08da579c5de7.root': {'conditionsTag': 'OFLCOND-RUN12-SDR-19',
    'beamType': 'collisions', 'fileType': 'RDO', 'geometryVersion': 'ATLAS-R2-2015-03-01-00', 'events': '3',
    'size': '3250143'}}

    :param workdir: payload work directory (str)
    :param filename: metadata file name (str)
    :return: metadata dictionary (dict).
    """
    # metadata_dictionary = { lfn: { att_name1: att_value1, .. }, ..}
    metadata_dictionary = {}
    path = os.path.join(workdir, filename)
    if not os.path.exists(path):
        logger.warning(f'file does not exist: {path}')
        return metadata_dictionary

    tree = ElementTree.parse(path)
    root = tree.getroot()
    # root.tag = POOLFILECATALOG

    for child in root:
        # child.tag = 'File', child.attrib = {'ID': '4ACC5018-2EA3-B441-BC11-0C0992847FD1'}
        lfn = ""
        guid = child.attrib['ID'] if 'ID' in child.attrib else None
        for grandchild in child:
            # grandchild.tag = 'logical', grandchild.attrib = {}
            if grandchild.tag == 'logical':
                for greatgrandchild in grandchild:
                    # greatgrandchild.tag = lfn
                    # greatgrandchild.attrib = lfn {'name': 'RDO_011a43ba-7c98-488d-8741-08da579c5de7.root'}
                    lfn = greatgrandchild.attrib.get('name')
                    metadata_dictionary[lfn] = {}
            elif grandchild.tag == 'metadata':
                # grandchild.attrib = {'att_name': 'events', 'att_value': '3'}
                name = grandchild.attrib.get('att_name')
                value = grandchild.attrib.get('att_value')
                metadata_dictionary[lfn][name] = value
            else:
                # unknown metadata entry
                pass
            if guid:
                metadata_dictionary[lfn]['guid'] = guid

    return metadata_dictionary


def get_number_of_events(metadata_dictionary: dict, filename: str = "") -> int:
    """
    Get the number of events for the given file from the metadata dictionary (from metadata.xml).

    :param metadata_dictionary: dictionary from parsed metadata.xml file (dict)
    :param filename: file name for which the number of events relates to (str)
    :return: number of events; -1 is returned if the events could not be extracted from the dictionary (int).
    """
    nevents = -1

    if filename != '' and filename in metadata_dictionary:
        try:
            nevents = int(metadata_dictionary[filename].get('events'))
        except ValueError as exc:
            logger.warning(f'failed to convert number of events to int: {exc}')
    else:
        logger.warning('number of events could not be extracted from metadata dictionary (based on metadata.xml)')

    return nevents


def get_total_number_of_events(metadata_dictionary: dict) -> int:
    """
    Get the total number of events for all files in the metadata dictionary.

    :param metadata_dictionary: dictionary from parsed metadata.xml file (dict)
    :return: total number of processed events (int).
    """
    nevents = 0

    for filename in metadata_dictionary:
        _nevents = get_number_of_events(metadata_dictionary, filename=filename)
        if _nevents != -1:
            nevents += _nevents

    return nevents


def get_guid(metadata_dictionary: dict, filename: str = "") -> str or None:
    """
    Get the guid from the metadata dictionary for the given LFN.

    :param metadata_dictionary: dictionary from parsed metadata.xml file (dict)
    :param filename: file name for which the number of events relates to (str)
    :return: guid (None is returned if guid could not be extracted) (str or None).
    """
    guid = None

    if filename != '' and filename in metadata_dictionary:
        try:
            guid = metadata_dictionary[filename].get('guid')
        except ValueError as exc:
            logger.warning(f'failed to get guid from xml: {exc}')
    else:
        logger.warning('guid could not be extracted from metadata dictionary (based on metadata.xml)')

    return guid


def get_guid_from_xml(metadata_dictionary: dict, lfn: str) -> str or None:
    """
    Get the guid for the given LFN in the metadata dictionary.

    :param metadata_dictionary: dictionary from parsed metadata.xml file (dict)
    :param lfn: LFN (str)
    :return: total number of processed events (int or None).
    """
    guid = None

    for filename in metadata_dictionary:
        if filename == lfn:
            guid = get_guid(metadata_dictionary, filename=filename)

    return guid
