# -*- coding: utf-8 -*-
#
# This file is part of the HvControllerGUI software.
# The HvController class contains methods to operate the HV device.
# It was developped for a FJ model +40kV 3.0 mA
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

import serial
import time
import logging

import checksum


class HvController():
    '''
    Class for controlling HV power supply Glassman FJ model +40kV 3.0 mA

    Modify constants according to specifications of the device:
       MAX_VOLTAGE = 40.0

       MAX_CURENT = 3.0

       MAX_HEX_VAL_RECEIVE = 0x3FF

       MAX_HEX_VAL_SENT = 0xFFF

    '''

    MAX_VOLTAGE = 40.0
    MAX_CURENT = 3.0
    MAX_HEX_VAL_RECEIVE = 0x3FF
    MAX_HEX_VAL_SENT = 0xFFF

    def __init__(self):
        self.device = serial.Serial()
        self.voltage = 0
        self.current = 0
        self.hvOn = False
        self.fault = False
        self.ctrlMode = 'voltage'
        self.logger = logging.getLogger('hvController')

    def openPortHV(self, port, defaultTI=2):
        '''
        Open the port for communication with HV supply

        Parameters
        ----------
        portname : str
            Port name (default 'COM4')
        defaultTI : float
            default time out (default 2 sec)
        '''
        self.device.port = port
        self.device.timeout = defaultTI
        self.device.open()

    def closePortHV(self):
        '''
        Close the HV port and check if correctly closed

        Returns
        -------
        output : str
            Succesful or still open
        '''
        self.resetHV()
        self.device.close()
        if self.device.is_open is False:
            return ("Device on port {} has been closed succesfully"
                    .format(self.device.name))
        else:
            return ("The close command has failed: port {} is still open!"
                    .format(self.device.name))
            # TODO: handle closing error

    def queryHV(self, verbosity=False):
        '''
        HV controller method to query the HV (Q command)

        Parameters
        ----------
        verbosity : bool
            Set to True for verbose output

        Returns
        -------
        Status : str
            return str of the status if verbosity set to True

        Updated values
        --------------
        hvOn : bool
            True if HV is on
        fault : bool
            True if HV is faulty
        ctrlMode : str
            'voltage' or 'current'
        voltage : float
            Voltage value in kV
        current : float
            Current value in mA
        '''
        self.device.read_all()

        queryCmd = self._encodeCommand('Q')
        answer = self._sendCommand(queryCmd)
        checksum.checkChecksum(answer)

        controlMode = {'0': 'voltage', '1': 'current'}
        faultStatus = {'0': False, '1': True}
        hvOnStatus = {'0': False, '1': True}

        # First extract the HV status and update the status
        statusBits = bin(int(answer[10:11], 16)).lstrip('0b').zfill(3)
        self.hvOn = hvOnStatus[statusBits[0]]
        self.fault = faultStatus[statusBits[1]]
        self.ctrlMode = controlMode[statusBits[2]]

        # Then extract the HV voltage and current values
        voltageByte = answer[1:4]
        curentByte = answer[4:7]

        self.voltage = round(int(voltageByte, 16)
                             * self.MAX_VOLTAGE / self.MAX_HEX_VAL_RECEIVE, 1)
        self.current = round(int(curentByte, 16)
                             * self.MAX_CURENT / self.MAX_HEX_VAL_RECEIVE, 1)

        if verbosity:
            return ('HV status: \n V = {v} \n I = {A}'
                    '\n HV mode : {mode} \n HV fault: {f} \n HV on: {on}'
                    .format(v=self.voltage, A=self.current, mode=self.ctrlMode,
                            f=self.fault, on=self.hvOn))

    def setHV(self, voltToSet, curToSet, digitContr='on', verbosity=False):
        '''
        HV controller method to send a set HV command (S command)

        Parameters
        ----------
        voltToSet : float
            Voltage in kV rounded to 0.01 precision
        curToSet : float
            Current in mA rounded to 0.01 precision
        digitContr : str
            'on' 'off' or 'reset'
        verbosity : bool
            Set to True for verbose output

        Returns
        -------
        Output : str
            return str succes or failed if verbosity set to True

        Updated values by a query after the execution:
        ----------------------------------------------
        hvOn : bool
            True if HV is on
        fault : bool
            True if HV is faulty
        ctrlMode : str
            'voltage' or 'current'
        voltage : float
            Voltage value in kV
        current : float
            Current value in mA
        '''

        # Construct the S commmand
        # Voltage and current are given in % of MAX_VALUE
        voltHex = round(voltToSet * self.MAX_HEX_VAL_SENT / self.MAX_VOLTAGE)
        curHex = round(curToSet * self.MAX_HEX_VAL_SENT / self.MAX_CURENT)

        # "%0.3X" % voltHex for 3 digit uppercase hex value
        if digitContr == 'off':
            cmd = 'S' + "%0.3X" % voltHex + "%0.3X" % curHex + '0000001'
        elif digitContr == 'on':
            cmd = 'S' + "%0.3X" % voltHex + "%0.3X" % curHex + '0000002'
        elif digitContr == 'reset':
            cmd = 'S' + "%0.3X" % 0 + "%0.3X" % 0 + '0000004'

        cmdToSend = self._encodeCommand(cmd)
        answer = self._sendCommand(cmdToSend, readTI=0.5)

        # Handle the answer
        if verbosity:
            if answer == b'A':
                return ("The set command sent succesfully: {} V, {} mA "
                        .format(voltToSet, curToSet))
            else:
                return ("Set command has failed \n Returned answer: {}"
                        .format(answer))

        # update of the HV status values
        self.queryHV()

    def version(self):
        '''
        HV controller method to ask the Version number (V command)

        The version number is encoded on bytes 1-2

        Returns
        -------
        Output : str
            Return version number

        '''

        cmdToSend = self._encodeCommand('V')
        answer = self._sendCommand(cmdToSend)
        checksum.checkChecksum(answer)
        return ("The firmware version is: {}"
                .format(answer[1:-2].decode()))

    def resetHV(self, verbosity=False):
        '''
        HV controller method to send a reset HV command (S command)

        Send a set HV method with digitContr = 'reset' so output is the
        same as setHV() method. Refer to it for details.

        Parameters
        ----------
        verbosity : bool
            Set to True for verbose output

        Returns
        -------
        Output : str
            Return str succes or failed if verbosity set to True

        Updated values by a query after the execution
        ---------------------------------------------
        hvOn : bool
            True if HV is on
        fault : bool
            True if HV is faulty
        ctrlMode : str
            'voltage' or 'current'
        voltage : float
            Voltage value in kV
        current : float
            Current value in mA

        '''

        output = self.setHV(0.0, 0.0, 'reset', verbosity)

        return output

    def _configureHV(self, timeoutMode="enable"):
        '''
        HV controller method to switch timeout mode ('enable' or 'disable')

        WARNING
        -------
        The timeout mode should always be enabled when the power
        supply is in normal use !!!

        Disable the timeout only for software debugging purposes!!!

        Parameters
        ----------
        timeoutMode : str
            'enable' or 'disable'
        Returns
        -------
        console output : str
            prints to the console : enabled or disabled

        '''
        if timeoutMode == "enable":
            configCmd = self._encodeCommand('C0')
            answer = self._sendCommand(configCmd)
            if answer is b'A':
                print("The timeout has been enabled")
            else:
                print(answer)

        elif timeoutMode == "disable":
            configCmd = self._encodeCommand('C1')
            answer = self._sendCommand(configCmd)
            if answer is b'A':
                print("The timeout has been disabled")
            else:
                print(answer)

    def _sendCommand(self, cmdToSend, readTI=0.1):
        '''
        HV controller method to send command to HV

        Parameters
        ----------
        cmdToSend : bytes
            Format b'\\\\x01XXXXXXX\\\\x0D'
        readTI : float
            Timeout for read method (default 0.1 s)
        Returns
        -------
        Answer : bytes
            return the answer received in bytes

        '''
        self.device.read_all()
        self.device.write(cmdToSend)
        time.sleep(readTI)
        answer = self.device.read_all().strip(b'\r')
        if answer.startswith(b'E'):
            self._handleError(answer)
        else:
            return answer

    def _encodeCommand(self, cmd):
        '''
        HV controller method to encode command from string to bytes

        Convert the string command into a bytes object, prepend the
        SOH character and append the checksum as well as the
        CR character

        Parameters
        ----------
        cmd : str
            String part of the command (e.g. Q051) including checksum

        Returns
        -------
        Command : bytes
            Return the command bytes (e.g. b'\\\\x01Q051\\\\x0D')

        '''
        csum = checksum.calculateChksum(cmd)
        cmdToSend = b'\x01' + bytes(cmd, 'ascii') + csum + b'\x0D'

        return cmdToSend

    def _handleErrors(self, errorMes):
        '''
        HV controller method to decode received error message

        Parameters
        ----------
        errorMes : bytes
            Error message stripped for b'\\\\r'

        Returns
        -------
        message : str
            Return the error message

        Note
        ----
        Not in use in the current version

        '''
        errorKey = int(errorMes.lstrip(b'E').decode('ascii')[0])
        errorDict = {1: "Undefined Command Code",
                     2: "Checksum Error",
                     3: "Extra Byte(s) received",
                     4: "Illegal Digital Control Byte In Set Command",
                     5: "Illegal Set Command Received While a Fault is Active",
                     6: "Processing Error"}
        return ("An error has occured: {}".format(errorDict[errorKey]))
