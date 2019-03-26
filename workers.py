# -*- coding: utf-8 -*-
#
# This file is part of the HvControllerGUI software.
# HvWorkers contains worker threads used to keeping the GUI responsive.
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

import traceback
import sys
from PyQt5 import QtCore


class HvSignals(QtCore.QObject):
    '''
    Signals available for aworker thread (Query, Set HV and Reset methods)

    Supported signals
    -----------------
    done : no data
        Emitted when thread ends
    output : str
        Output string of the command
    error : tuple
        Error traceback
    '''
    #: obj: pyqtSignal() Emitted when thread ends
    done = QtCore.pyqtSignal()
    #: obj: pyqtSignal(str) Output string of the command
    output = QtCore.pyqtSignal(str)
    #: obj: pyqtSignal(tuple) Error traceback
    error = QtCore.pyqtSignal(tuple)


class HvWorker(QtCore.QRunnable):
    ''' QRunnable worker for Query, Set HV and Reset methods of the GUI '''

    def __init__(self, fn, *args, **kwargs):
        super(HvWorker, self).__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = HvSignals()

    @QtCore.pyqtSlot()
    def run(self):
        try:
            output = self.fn(*self.args, **self.kwargs)
        # TODO: add a specific exception name
        except :
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            self.signals.output.emit(output)
        finally:
            self.signals.done.emit()
