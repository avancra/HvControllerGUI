# -*- coding: utf-8 -*-
#
# This file is part of the HvControllerGUI software.
# The checksum module provides functions to calculate and check
# the checksum for commands in bytes format. The provided functions
# are tuned for use with a Glassman HV power supply.
#
# Copyright 2018-2019 Aurélie Vancraeyenest
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


def calculateChksum(cmd):
    '''
    Return the checksum value in ASCII coded hexadecimal

    Parameters
    ----------
    cmd : str
        String part of the command (e.g. Q051)

    Returns
    -------
    checksum : bytes
        Checksum value in bytes in the form b'XX'

    '''
    arr = bytearray(cmd, 'ascii')
    checksum = bytes(hex(sum(arr) % 256), 'ascii')   # in form  b'0x21'

    return checksum.lstrip(b'0x').zfill(2).upper()


def checkChecksum(mesToCheck):
    '''
    Compare the checksum value recieved to the calculated one

    Extract the checksum value from the incoming message and compare it
    to the checksum calculated from the rest of the message

    Parameters
    ----------
    mesToCheck : bytes
        message from HV stripped from b'\\\\r', in bytes()

    Raises
    ------
    AssertionError
        If the received and the calculated checksum do not match
    '''

    csumRed = mesToCheck[-2:]
    csumCalc = calculateChksum(mesToCheck[1:-2].decode())

    try:
        assert csumRed == csumCalc
    except AssertionError:
        print('WARNING : Checksum error in the incoming message !')
        # raise ??
