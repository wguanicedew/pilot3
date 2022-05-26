#!/usr/bin/env python
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0
#
# Authors:
# - Paul Nilsson, paul.nilsson@cern.ch, 2022


def mv_to_final_destination():
    """
    Is mv allowed to move files to final destination?
    In ATLAS, the Pilot will only move the output to a local directory. The aCT will pick it up from there and move it
    to the final destination.
    :return: Boolean.
    """

    return False
