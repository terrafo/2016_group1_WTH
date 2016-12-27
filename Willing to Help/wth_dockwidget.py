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

from PyQt4.QtCore import QTimer
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

        self.timer = QTimer()
        self.timer.timeout.connect(self.user_autopositioning)

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
        #self.text_field.setStyleSheet("#myFrameName { border-style: solid; border-width: 5px; }")

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

        # Dictionary of active shapefiles displayed
        self.active_shpfiles = {}

        # Total list of layers actually displayed on map canvas
        #self.canvas_layers = []

        # Set Button connections
        self.pushButton_yes.clicked.connect(self.will_to_help)
        self.pass_check_btn.clicked.connect(self.login_correct)
        self.menu_settings_btn.clicked.connect(self.toggle_refresher)
        # Hide none init layers
        self.top_bar.hide()
        self.wth_popup.hide()

        self.load_shapefiles(["user_pos", "tasks", "road_network"])
        self.refresh_extent("user_pos")

        # Show init layer
        getattr(self.pass_popup, "raise")()

    def load_shapefiles(self, shp_files):
        # Prepare Map Canvas
        # Current path
        cur_path = os.path.dirname(os.path.abspath(__file__))

        # Map path
        source_dir = "/DB/shapefile_layers"

        # load vector layers
        for file in shp_files:  # os.listdir(cur_path+source_dir): # To read the path
            #  if file.endswith(".shp"):  # load only the shapefiles

            # TODO Build dictionary to link to shapefiles
            # TODO Create function to use extends based on specific shapefiles
            # TODO Create Thread to update the Canvas
            # create vector layer object
            vlayer = QgsVectorLayer(cur_path+source_dir + "/" + file + ".shp", file, "ogr")

            # Add the layer to the dictionary
            self.active_shpfiles[file] = [vlayer, QgsMapCanvasLayer(vlayer)]

            # add the layer to the registry
            QgsMapLayerRegistry.instance().addMapLayer(vlayer)

            #self.canvas_layers.append(QgsMapCanvasLayer(vlayer))

        #added_shpfiles = [self.active_shpfiles[x][0] for x in shp_files]  # List only new shpfiles
        added_canvaslayers = [self.active_shpfiles[x][1] for x in shp_files]  # List only new canvaslayers

        # provide set of layers for display on the map canvas
        self.map_canvas.setLayerSet(added_canvaslayers)

    def refresh_extent(self, layer_to_load):

        #self.extent.setMinimal() # TODO is this really needed?

        if layer_to_load == "user_pos":
            user_point = [feat for feat in self.active_shpfiles["user_pos"][0].getFeatures()]
            user_pos = user_point[0].geometry().asPoint()

            self.extent = QgsRectangle(user_pos[0] - 197.9, user_pos[1] - 255,
                                       user_pos[0] + 195.1, user_pos[1] + 295)
        else:
            print "User selected a task"

        #zoomRectangle = QgsRectangle(pos[0] - offset, pos[1] - offset, pos[0] + offset, pos[1] + offset)
        #self.canvas.setExtent(zoomRectangle)

        #for file in layers_to_load: #TODO FIX if not many files
        #    # combine extent of the current vector layer with the extent of the created "extent" rectangle object
        #    self.extent.combineExtentWith(self.active_shpfiles[file][0].extent())  # Use that for merged extent of all layers

        # set extent to the extent of a larger rectangle so we can see all geometries
        self.map_canvas.setExtent(self.extent)  # Use that for merged extent of all layers
        #self.map_canvas.setExtent(vlayer.extent())  # Use that for extent of a specific layer

        #self.canvas.refresh() # TODO might need
        # Rerender the layer
        self.active_shpfiles[layer_to_load][0].triggerRepaint()
        #self.canvas.freeze(True)

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()
        self.timer.stop()

    def will_to_help(self):
        self.wth_popup.hide()
        self.top_bar.show()
        #self.menu_group_btn.show()
        #self.menu_layers_btn.show()
        #self.menu_settings_btn.show()
        getattr(self.top_bar, "raise")()
        getattr(self.menu_group_btn, "raise")()
        getattr(self.menu_layers_btn, "raise")()
        getattr(self.menu_settings_btn, "raise")()
        self.menu_group_btn.show()
        self.menu_layers_btn.show()
        self.menu_settings_btn.show()
        print "Lets get down to business"

    def toggle_refresher(self):
        if not self.timer.isActive():
            self.timer.start(1000)
        else:
            self.timer.stop()

    def user_autopositioning(self):
        self.refresh_extent("user_pos")

    def login_correct(self):
        # Hide login layer
        self.pass_popup.hide()

        # Show next layer
        self.wth_popup.show()
        getattr(self.wth_popup, "raise")()  #getattr(self.pass_popup, "lower")()  # Might be the opposite
        print "done"
