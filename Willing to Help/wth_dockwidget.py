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
from PyQt4 import QtCore, uic
from PyQt4.QtGui import QWidget, QLabel, QHBoxLayout, QVBoxLayout, QDockWidget, QPixmap
from qgis.core import *
from qgis.networkanalysis import *
from qgis.gui import *
import processing
import datetime

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

class WTH_DockWidget(QDockWidget, FORM_CLASS):

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

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.refresher)

        #Makes the Widget Undockable
        #self.setAllowedAreas(QtCore.Qt.NoDockWidgetArea)

        # Makes the Widget to be like a popup
        #self.setFloating(True)

        #self.isActiveWindow()
        #self.setFeatures(QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetMovable)
        #print self.windowState()
        #self.setWindowState(QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
        #self.updateGeometry()
        #self.windowState()

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
        #self.menu_settings_btn.clicked.connect()
        self.menu_settings_btn.setStyleSheet("QPushButton#menu_settings_btn:checked {background: transparent;}")

        self.menu_layers_btn.clicked.connect(self.check_events)
        self.task_list_back_btn.clicked.connect(self.close_check_events)
        #self.task_list_back_btn.clicked.connect(self.add_new_label)

        # Hide none init layers
        self.top_bar.hide()
        self.wth_popup.hide()
        self.task_list.hide()

        self.load_shapefiles(["user_pos", "tasks", "road_network"])

        # Convert tasks into a dictionary
        self.task_dict = self.task_parser(self.active_shpfiles["tasks"][0])

        # Build icons dictionaries
        self.event_icons = {1: "EventPriority1.png", 2: "EventPriority2.png", 3: "EventPriority3.png"}
        self.group_icons = {0: "Group_Icon0.png", 1: "Group_Icon1.png", 2: "Group_Icon2.png"}

        #Container Widget
        self.event_widget = QWidget()  # Set name: #self.stats_scrollarea.setObjectName("stats_scrollArea")
        self.event_widget.setStyleSheet("QWidget{background: transparent}")

        self.refresh_extent("user_pos")
        self.refresh_event_list()

        # Show init layer
        getattr(self.pass_popup, "raise")()

    def refresh_event_list(self):

        #label = QLabel("new")
        #self.events_vertical_layout.layout().addWidget(label)

        #Layout of Container Widget
        layout = QVBoxLayout(self)
        for event, attr in self.task_dict.iteritems():
            event_layout = QHBoxLayout(self)

            event_icon_path = os.path.dirname(os.path.abspath(__file__)) + "/graphics/" + self.event_icons[attr["priority"]]
            event_icon = QLabel()
            event_icon.setGeometry(0, 0, 16, 29)
            event_icon.setMinimumWidth(16)
            event_icon.setMaximumWidth(16)
            event_icon.setPixmap(QPixmap(event_icon_path))
            event_layout.addWidget(event_icon)

            event_text_layout = QVBoxLayout(self)
            event_text_layout.setSpacing(0)

            event_title = QLabel(attr["title"])
            event_title.setStyleSheet("QLabel {font-family: Impact; font-size: 17pt; color: white;}")
            event_title.setMinimumHeight(35)
            event_title.setMaximumWidth(220)
            event_text_layout.addWidget(event_title)

            event_skills = QLabel("Hammer, Dog, Money")
            event_skills.setStyleSheet("QLabel {font-family: Roboto; font-size: 11pt; color: white;}")
            event_skills.setMaximumWidth(220)
            event_text_layout.addWidget(event_skills)

            event_layout.addLayout(event_text_layout)

            group_icon_path = os.path.dirname(os.path.abspath(__file__)) + "/graphics/" + self.group_icons[attr["group"]]
            group_icon = QLabel()
            group_icon.setGeometry(0, 0, 34, 34)
            group_icon.setMinimumWidth(34)
            group_icon.setMaximumWidth(34)
            group_icon.setPixmap(QPixmap(group_icon_path))
            event_layout.addWidget(group_icon)

            event_title.mouseReleaseEvent = self.check_about_event

            layout.addLayout(event_layout)

        self.event_widget.setLayout(layout)
        self.events_scrollArea.setWidget(self.event_widget)

    def check_about_event(self, *args):
        print "Check About"
        #label = QLabel("new")
        #self.event_widget.layout().addWidget(label)

    def load_shapefiles(self, shp_files):
        # Prepare Map Canvas
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

    def refresher(self):
        if not self.menu_settings_btn.isChecked():
            print "WTF"
        else:
            self.refresh_extent("user_pos")

    def task_parser(self, layer):
        event_dict = {}
        # fields = [field.name() for field in layer.pendingFields()]  # Get attributes
        request = QgsFeatureRequest()
        request.setFlags(QgsFeatureRequest.NoGeometry)
        for feature in layer.getFeatures(request):
            # attrs is a list. It contains all the attribute values of this feature
            attrs = feature.attributes()
            event_dict[attrs[0]] = {'timed': attrs[1], 'title': attrs[2], 'about': attrs[3], 'group': attrs[4],
                                    'missing': attrs[5], 'priority': attrs[6]}
        return event_dict

    def check_events(self):
        self.task_list.show()

    def close_check_events(self):
        self.task_list.hide()

    def login_correct(self):
        # Hide login layer
        self.pass_popup.hide()

        # Show next layer
        self.wth_popup.show()
        getattr(self.wth_popup, "raise")()  #getattr(self.pass_popup, "lower")()  # Might be the opposite
        print "done"
