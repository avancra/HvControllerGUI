# -*- coding: utf-8 -*-
#
# HvControllerGUI is designed to operate a HV power supply from
# Glassman remotely through a graphical user interface. It was developped
# for a FJ model +40kV 3.0 mA
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

import sys
import logging
import datetime
import webbrowser
from PyQt5 import QtWidgets, QtCore, QtGui

import serial
from serial.tools import list_ports

import HvGUI
import HvController as hv
import workers

ICON_RED_LED = ":/icons/led-red-on.png"
ICON_GREEN_LED = ":/icons/green-led-on.png"


class MainWindow(QtWidgets.QMainWindow, HvGUI.Ui_MainWindow):
    '''
    Main instance for the GUI of the HV controller panel

    HvControllerGUI is designed to operate a HV power supply from
    Glassman remotely through a graphical user interface. It was
    developped for use with a FJ model +40kV 3.0 mA.

    It makes use of QRunnables and QThreadPool for running small
    repetitive opperations without freezing the GUI. It also makes
    extensive use of PyQt signal and slot design for communication
    between threads.

    '''

    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        self.setupUi(self)

        # Setup application logger
        self.logger = logging.getLogger('hvController')
        self.logger.setLevel(logging.INFO)
        # create file handler which logs info messages
        fh = logging.FileHandler('hvCtrl.log', mode='w')
        fh.setLevel(logging.INFO)
        # create formatter and add it to the handler
        formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        # add the handler to the logger
        self.logger.addHandler(fh)

        self.hvdevice = hv.HvController()
        self.querytimer = QtCore.QTimer()
        self.checktimer = QtCore.QTimer()
        self.setupTimers()
        self.threadpool = QtCore.QThreadPool()
        self._setupUiDesign()

        # Extract some useful values from the GUI
        self.targetHV = self.voltValueToSet.value()
        self.targetI = self.curValueToSet.value()
        # TODO : add settings for saving preferences

    def _setupUiDesign(self):
        '''Prepare the initial desgin of the GUI. '''
        self.voltValueToSet.setMaximum(self.hvdevice.MAX_VOLTAGE)
        self.curValueToSet.setMaximum(self.hvdevice.MAX_CURENT)
        self.disableAll()
        for name, desc, add in sorted(list_ports.comports()):
            self.prtList.addItem(name)
        # Put COM4 port as default: adapt to workstation or improve
        # and implement with QSettings
        if self.prtList.findText('COM4') >= 0:
            self.prtList.setCurrentIndex(self.prtList.findText('COM4'))

    def setupTimers(self):
        '''Configure the timers for query and stability check'''
        # The Glassman HV has a communication timeout of 1.5 s
        # so we perform a query every 500 ms
        self.querytimer.setInterval(500)
        self.querytimer.timeout.connect(self.hvdevice.queryHV)
        self.querytimer.timeout.connect(self.updateStatus)

        self.checktimer.setInterval(60000)  # can be changed to longer
        self.checktimer.timeout.connect(self.checkStability)

        self.now = datetime.datetime.today()
        self.lastEntryTime = datetime.datetime.today()

    # ---------------- Slots --------------
    # define here pyqtslot using connectSlotsByName() convention
    @QtCore.pyqtSlot()
    def on_actionAbout_triggered(self):
        self.showMessage("HvControllerGUI Copyright (C) 2018-2019 "
                         "Aurélie Vancraeyenest"
                         "\n\n This program is licensed under the"
                         " Apache License, Version 2.0 "
                         "\n\nThis program comes with ABSOLUTELY NO WARRANTY."
                         "\nThis is free software, and you are welcome to "
                         "redistribute it under certain conditions. "
                         "See LICENSE file for details.")

    @QtCore.pyqtSlot()
    def on_actionHV_firmware_version_triggered(self):
        if self.hvdevice.device.is_open:
            message = self.hvdevice.version()
            self.showMessage(message)
        else:
            self.showMessage('The device COM port should be open'
                             ' to get the firmware version.'
                             '\nOpen the port and try again.')

    @QtCore.pyqtSlot()
    def on_actionOnline_documentation_triggered(self):
        webbrowser.open('https://github.com/avancra/HvControllerGUI')

    @QtCore.pyqtSlot()
    def on_prtOpenBtn_clicked(self):
        '''
        Open the selected port and instantiate an HV controller

        Get the port from the GUI, open it and init the hv controler.
        If success, start a timer which will query the HV every 0.5s.
        '''
        # ??? : check for opened port and close it
        portName = self.prtList.currentText()

        try:
            self.hvdevice.openPortHV(portName)
        except serial.SerialException:
            QtWidgets.QMessageBox.warning(
                    self, 'HV ctrl',
                    'Serial Exception: could not open the {} port'
                    .format(portName))
        else:
            self.querytimer.start()
            self.checktimer.start()
            self.enableAll()
            self.prtList.setEnabled(False)
            self.prtOpenBtn.setEnabled(False)
            self.updateStatus()

    @QtCore.pyqtSlot()
    def on_prtCloseBtn_clicked(self):
        ''' Close the current port and disable the GUI widget once closed '''

        self.querytimer.stop()
        try:
            output = self.hvdevice.closePortHV()
        except serial.SerialException:
            QtWidgets.QMessageBox.warning(
                    self, 'HV ctrl',
                    '''Serial Exception: could not close the {} port'''
                    .format(self.hvdevice.device.port))
        else:
            self.prtList.setEnabled(True)
            self.prtOpenBtn.setEnabled(True)
            self.disableAll()
            self.cmdOutText.append(output)

    @QtCore.pyqtSlot()
    def on_queryBtn_clicked(self):
        '''
        Method to launch the query thread worker through the threadpool

        Keyword arguments
        -----------------
        verbosity : bool
        '''

        queryWk = workers.HvWorker(self.hvdevice.queryHV)
        queryWk.kwargs['verbosity'] = True
        queryWk.signals.output.connect(self.printOutput)
        queryWk.signals.done.connect(self.updateStatus)
        queryWk.signals.done.connect(self.querytimer.start)

        self.querytimer.stop()
        self.threadpool.start(queryWk)

    @QtCore.pyqtSlot()
    def on_setBtn_clicked(self):
        '''
        Method to launch the set HV thread worker through the threadpool

        Keyword arguments
        -----------------
        voltToSet : float
            voltage
        curToSet : float
            current
        verbosity : bool
        '''
        self.targetHV = round(self.voltValueToSet.value(), 2)
        self.targetI = round(self.curValueToSet.value(), 2)
        setWk = workers.HvWorker(self.hvdevice.setHV)
        setWk.kwargs['voltToSet'] = self.targetHV
        setWk.kwargs['curToSet'] = self.targetI
        setWk.kwargs['verbosity'] = True

        setWk.signals.done.connect(self.updateStatus)
        setWk.signals.done.connect(self.querytimer.start)
        setWk.signals.output.connect(self.printOutput)

        self.querytimer.stop()
        self.threadpool.start(setWk)

    @QtCore.pyqtSlot()
    def on_resetBtn_clicked(self):
        '''
        Method to launch the reset HV thread worker through the threadpool

        Keyword arguments
        -----------------
        verbosity : 'bool'
        '''
        self.voltValueToSet.setValue(0.0)
        self.curValueToSet.setValue(0.0)
        self.targetHV = 0.0
        self.targetI = 0.0

        resetWK = workers.HvWorker(self.hvdevice.resetHV)
        resetWK.kwargs['verbosity'] = True

        resetWK.signals.done.connect(self.updateStatus)
        resetWK.signals.done.connect(self.querytimer.start)
        resetWK.signals.output.connect(self.printOutput)

        self.querytimer.stop()
        self.threadpool.start(resetWK)

    @QtCore.pyqtSlot()
    def on_actionExit_triggered(self):
        self.querytimer.stop()
        self.checktimer.stop()
        if self.hvdevice.device.is_open:
            self.hvdevice.closePortHV()
        self.close()

    # ---------------- Other slots --------------
    # define here other pyqtslots
    @QtCore.pyqtSlot()
    def updateStatus(self):
        '''
        Update the values/icons of the GUI corresponding to the HV status

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

        self.voltValueRead.display(self.hvdevice.voltage)
        self.curValueRead.display(self.hvdevice.current)
        if self.hvdevice.ctrlMode == "voltage":
            self.ctrlModeVoltBtn.setChecked(True)
        elif self.hvdevice.ctrlMode == "current":
            self.ctrlModeCurBtn.setChecked(True)

        if self.hvdevice.hvOn is True:
            self.hvOnLed.setPixmap(QtGui.QPixmap(ICON_GREEN_LED))
        elif self.hvdevice.hvOn is False:
            self.hvOnLed.setPixmap(QtGui.QPixmap(ICON_RED_LED))
        else:
            self.hvOnLed.setEnabled(False)

        if self.hvdevice.fault is True:
            self.faultLed.setPixmap(QtGui.QPixmap(ICON_RED_LED))
        else:
            self.faultLed.setEnabled(False)

    @QtCore.pyqtSlot(str)
    def printOutput(self, s):
        '''
        Append command outputs to the text box of the GUI

        Parameters
        ----------
        s : str
            emitted via threadpool threads
        '''
        self.cmdOutText.append(s)

    @QtCore.pyqtSlot()
    def checkStability(self):
        ''' Check if the voltage is within a 0.2 V from the targetted one '''
        delta = 0.2
        if (self.targetHV-delta < self.hvdevice.voltage < self.targetHV+delta):
            # if last log entry more than 1min:
            self.makeLogEntry('HV stability ok: %.2f',
                              value=self.hvdevice.voltage, level='info')
        else:
            self.makeLogEntry('HV stability fails: %.2f',
                              value=self.hvdevice.voltage, level='warning')
            self.makeLogEntry('Try to return to target value...  %.2f',
                              value=self.targetHV, level='warning')
            self.on_setBtn_clicked()
            if (self.targetHV-delta < self.hvdevice.voltage < self.targetHV+delta):
                self.makeLogEntry('HV back to target voltage: %.2f',
                                  value=self.hvdevice.voltage, level='info')
            else:
                self.makeLogEntry('Tentative failed, voltage value: %.2f',
                                  value=self.hvdevice.voltage, level='warning')

    @QtCore.pyqtSlot()
    def programEnded(self):
        QtWidgets.QMessageBox.warning(self, "Warning", "Thread is done")

    # --------------- Other class methods --------
    def disableAll(self):
        ''' Disable all the widgets for HV control of the GUI '''

        self.voltValueToSet.setEnabled(False)
        self.curValueToSet.setEnabled(False)
        self.queryBtn.setEnabled(False)
        self.setBtn.setEnabled(False)
        self.resetBtn.setEnabled(False)
        self.faultLed.setEnabled(False)
        self.hvOnLed.setEnabled(False)
        self.prtCloseBtn.setEnabled(False)
        self.prgSelectBtn.setEnabled(False)
        self.prgStartBtn.setEnabled(False)
        self.prgStopBtn.setEnabled(False)
        self.prgPlotVoltBtn.setEnabled(False)
        self.prgFilenameLineEdit.setEnabled(False)

    def enableAll(self):
        ''' Enable all the widgets of the GUI for HV control '''

        self.voltValueToSet.setEnabled(True)
        self.curValueToSet.setEnabled(True)
        self.queryBtn.setEnabled(True)
        self.setBtn.setEnabled(True)
        self.resetBtn.setEnabled(True)
        self.faultLed.setEnabled(True)
        self.hvOnLed.setEnabled(True)
        self.prtCloseBtn.setEnabled(True)
        # for future use when functionnality is implemented
#        self.prgSelectBtn.setEnabled(True)
#        self.prgStartBtn.setEnabled(True)
#        self.prgStopBtn.setEnabled(True)
#        self.prgPlotVoltBtn.setEnabled(True)
#        self.prgFilenameLineEdit.setEnabled(True)

    def showMessage(self, message):
        '''
        Display a message in an "Information" message box with 'OK' button.

        Parameters:
        -----------
        message : str
            Message to print in the message box
        '''

        messageBox = QtWidgets.QMessageBox()
        messageBox.setText(message)
        messageBox.setWindowTitle("Info")
        messageBox.setIcon(QtWidgets.QMessageBox.Information)
        messageBox.setStandardButtons(QtWidgets.QMessageBox.Ok)
        messageBox.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)

        # Show the window
        messageBox.raise_()
        messageBox.exec_()

    def makeLogEntry(self, message, **kwargs):
        '''
        Make a new entry if the last one was done less than 10 min ago

        Parameters
        ---------
        message : str
            Message to print to the log file
        kwargs : dict
            keyword arguments

        keyword arguments
        -----------------
        value : obj
            Variable to log (type must match the format given in the message)
        level : str
            Level of the log entry (lower case)
        '''

        self.now = datetime.datetime.today()
        dtime = self.now - self.lastEntryTime
        if dtime.total_seconds()/60 > 10:
            if kwargs['level'] == 'debug':
                self.logger.debug(message, kwargs['value'])
                self.lastEntryTime = self.now
            elif kwargs['level'] == 'info':
                self.logger.info(message, kwargs['value'])
                self.lastEntryTime = self.now
            elif kwargs['level'] == 'warning':
                self.logger.warning(message, kwargs['value'])
                self.lastEntryTime = self.now
            elif kwargs['level'] == 'error':
                self.logger.error(message, kwargs['value'])
                self.lastEntryTime = self.now
            elif kwargs['level'] == 'critical':
                self.logger.critical(message, kwargs['value'])
                self.lastEntryTime = self.now


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    form = MainWindow()
    form.show()
    app.exec()
