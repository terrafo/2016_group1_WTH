# -*- coding: utf-8 -*-
"""
/***************************************************************************
Willing to Help (WTH) is a QGIS 2.14 plugin, which will be developed as a part
of the course GEO1005 of Master of Geomatics. The plugin will take simulated
and timed data to manage and track volunteered resources in a disaster situation
in the Netherlands.
                             -------------------
        begin                : 2016-12-12
        copyright            : (C) 2016 by Panagiotis Karydakis, Kotryna Valečkaitė, Dimitris Xenakis
        email                : sparkdevelopment.social@gmail.com
        git sha              : $Format:%H$
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

#TODO clean the unused imports
from PyQt4 import QtGui, QtCore, uic
from qgis.core import *
from qgis.networkanalysis import *
from qgis.gui import *
import processing

# matplotlib for the charts
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

import os
import random
import csv
import time

from . import utility_functions as uf

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'wth_dockwidget_base.ui'))

class WTH_DockWidget(QtGui.QDockWidget, FORM_CLASS):

    closingPlugin = QtCore.pyqtSignal()
    updateAttribute = QtCore.pyqtSignal(str)

    def __init__(self, iface, parent=None):
        """Constructor."""
        super(WTH_DockWidget, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)

        # define globals
        self.iface = iface
        self.canvas = self.iface.mapCanvas()


        #Makes the Widget Undockable
        #self.setAllowedAreas(QtCore.Qt.NoDockWidgetArea)

        # Makes the Widget to be like a popup
        #self.setFloating(True)

        #self.isActiveWindow()
        #self.setFeatures(QtGui.QDockWidget.DockWidgetClosable | QtGui.QDockWidget.DockWidgetMovable)
        #print self.windowState()
        #self.setWindowState(QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
        #self.updateGeometry()
        #self.windowState()

        #self.text_field = QtGui.QPlainTextEdit(self)
        #self.text_field.setMinimumSize(381, 722)
        #self.text_field.setStyleSheet("background-image: url(:graphics/Phone_Template.png);")

        #self.setStyleSheet("""
        #    .WTH_DockWidget {
        #        border: 20px solid black;
        #        border-radius: 10px;
        #        background-color: rgb(5, 255, 255);
        #        background-image: url(:graphics/Phone_Template.png);
        #        }
        #    """)

        #movie = QtGui.QMovie(':icons/loading2.gif')
        #self.logoLabel.setMovie(movie)
        #movie.start()

        #Form.setStyleSheet("QWidget#Form {background-image: url(test.jpg);}")

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()
