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

from PyQt4 import QtGui, QtCore, uic

import os


from . import utility_functions as uf

FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), 'wth_dockwidget_base.ui'))


class WTH_DockWidget(QtGui.QDockWidget, FORM_CLASS):

    closingPlugin = QtCore.pyqtSignal()

    def __init__(self, iface, parent=None):
        """Constructor."""
        super(WTH_DockWidget, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)

        #print self # .setWindowFlags(QtCore.Qt.FramelessWindowHint)

    def closeEvent(self, event):
        # disconnect interface signals
        try:
            self.iface.projectRead.disconnect(self.updateLayers)
            self.iface.newProjectCreated.disconnect(self.updateLayers)
            self.iface.legendInterface().itemRemoved.disconnect(self.updateLayers)
            self.iface.legendInterface().itemAdded.disconnect(self.updateLayers)
        except:
            pass

        self.closingPlugin.emit()
        event.accept()