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
from PyQt4.QtGui import QWidget, QLabel, QHBoxLayout, QVBoxLayout, QDockWidget, QPixmap, QPushButton
from qgis.core import *
from qgis.networkanalysis import *
from qgis.gui import *
import processing
from datetime import datetime, timedelta

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
        self.setupUi(self)

        # define globals
        self.iface = iface
        self.canvas = self.iface.mapCanvas()

        # Set global timer and interval
        self.seconds_passed = 0
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.refresher)


        # Reference to the currently selected event
        self.selected_event = None

        # Dictionary of active shapefiles displayed
        self.active_shpfiles = {}

        # Set Button connections
        self.pushButton_yes.clicked.connect(self.will_to_help)
        self.pass_check_btn.clicked.connect(self.login_correct)
        self.menu_settings_btn.setStyleSheet("QPushButton#menu_settings_btn:checked {background: transparent;}")

        self.menu_layers_btn.clicked.connect(self.check_events)
        self.task_list_back_btn.clicked.connect(self.close_check_events)
        self.about_event_back_btn.clicked.connect(self.close_about_event)

        # Hide none init layers
        self.top_bar.hide()
        self.wth_popup.hide()
        self.task_list.hide()
        self.about_task.hide()

        self.load_shapefiles(["user_pos", "tasks", "road_network"])

        # Convert tasks into a dictionary
        self.task_dict = self.task_parser(self.active_shpfiles["tasks"][0])

        # Build icons dictionaries
        self.event_icons = {1: "EventPriority1.png", 2: "EventPriority2.png", 3: "EventPriority3.png"}
        self.group_icons = {0: "Group_Icon0.png", 1: "Group_Icon1.png", 2: "Group_Icon2.png"}

        # Container Widget
        self.event_widget = QWidget()  # Set name: #self.stats_scrollarea.setObjectName("stats_scrollArea")
        self.event_widget.setStyleSheet("QWidget{background: transparent}")

        # Refresh extent to user position
        self.refresh_extent("user_pos")
        # Refresh event list
        self.refresh_event_list()

        # Show init layer
        getattr(self.pass_popup, "raise")()

    def refresh_event_list(self):
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

            event_text_layout.addWidget(self.event_button_generator(event, attr))

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

            layout.addLayout(event_layout)

        self.event_widget.setLayout(layout)
        self.events_scrollArea.setWidget(self.event_widget)

    def event_button_generator(self, task_id, attr):
        btn = QPushButton(attr["title"])
        btn.setStyleSheet("QPushButton {font-family: Impact; font-size: 17pt; color: white; text-align: left;}")
        btn.setMinimumHeight(35)
        btn.setMaximumWidth(220)
        btn.clicked.connect(lambda: self.check_about_event(task_id, attr))
        return btn

    def check_about_event(self, task_id, attr):
        # Set current event id as the selected one
        self.selected_event = task_id

        group_icon_path = os.path.dirname(os.path.abspath(__file__)) + "/graphics/" + self.group_icons[attr["group"]]
        self.about_group_icon.setPixmap(QPixmap(group_icon_path))
        self.event_title.setText(attr["title"])
        self.group_missing_note.setText('Missing {} people for a full party.'.format(attr["missing"]))
        self.group_missing_note.setStyleSheet("QLabel {font-family: Roboto; font-size: 11pt; color: white; qproperty-alignment: AlignCenter AlignRight;}")
        about_text = "<html><b>This and this and that.</b</html><br><br>" + attr["about"]
        self.about_event_txt.setText(about_text)
        try:
            self.join_event.clicked.disconnect()
        except:
            pass

        # Bind join button to the corresponding function
        self.join_event.clicked.connect(lambda: self.join_event_started(task_id))

        # Zoom onto the selected event
        self.refresh_extent(task_id)

        # Hide the event list footer
        self.task_list.hide()

        # Show the about information of the selected event
        self.about_task.show()

    def join_event_started(self, event_id):
        print "go to", event_id
        self.about_task.hide()
        # No event is selected anymore
        self.selected_event = None
        # Reset event timer
        self.counter_event.setText("--:--:--")

    def load_shapefiles(self, shp_files):
        # Prepare Map Canvas
        cur_path = os.path.dirname(os.path.abspath(__file__))

        # Map path
        source_dir = "/DB/shapefile_layers"

        # load vector layers
        for file in shp_files:  # os.listdir(cur_path+source_dir): # To read the path
            # TODO Build dictionary to link to shapefiles
            # TODO Create function to use extends based on specific shapefiles
            # TODO Create Thread to update the Canvas
            # create vector layer object
            vlayer = QgsVectorLayer(cur_path+source_dir + "/" + file + ".shp", file, "ogr")

            # Add the layer to the dictionary
            self.active_shpfiles[file] = [vlayer, QgsMapCanvasLayer(vlayer)]

            # add the layer to the registry
            QgsMapLayerRegistry.instance().addMapLayer(vlayer)

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
            user_pos = self.task_dict[layer_to_load]["position"]
            self.extent = QgsRectangle(user_pos[0] - 197.9, user_pos[1] - 350,
                                       user_pos[0] + 195.1, user_pos[1] + 50)

        #zoomRectangle = QgsRectangle(pos[0] - offset, pos[1] - offset, pos[0] + offset, pos[1] + offset)
        #self.canvas.setExtent(zoomRectangle)

        #for file in layers_to_load: #TODO FIX if not many files
        #    # combine extent of the current vector layer with the extent of the created "extent" rectangle object
        #    self.extent.combineExtentWith(self.active_shpfiles[file][0].extent())  # Use that for merged extent of all layers

        # set extent to the extent of a larger rectangle so we can see all geometries
        self.map_canvas.setExtent(self.extent)  # Use that for merged extent of all layers
        #self.map_canvas.setExtent(vlayer.extent())  # Use that for extent of a specific layer

        #self.canvas.refresh() # TODO might need
        # Re-render the road network (along with everything else)
        self.active_shpfiles["road_network"][0].triggerRepaint()

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()
        self.timer.stop()

    def will_to_help(self):
        self.wth_popup.hide()
        self.top_bar.show()
        getattr(self.top_bar, "raise")()
        getattr(self.menu_group_btn, "raise")()
        getattr(self.menu_layers_btn, "raise")()
        getattr(self.menu_settings_btn, "raise")()
        self.menu_group_btn.show()
        self.menu_layers_btn.show()
        self.menu_settings_btn.show()
        print "Lets get down to business"

    def refresher(self):
        # Append to time fixed seconds
        self.seconds_passed += 4
        # Simulate new time
        self_simulated_time = datetime.today() + timedelta(0, self.seconds_passed)

        if not self.menu_settings_btn.isChecked():
            print "WTF"
        else:
            self.refresh_extent("user_pos")

        # If use has selected to view a specific event..
        if self.selected_event:
            # Event's end time
            e = datetime.strptime(self.task_dict[self.selected_event]["timed"], '%Y-%m-%d %H:%M:%S')

            # Time difference between simulated time and event's end time
            d = e - self_simulated_time
            event_timer = '{0:0=2d}:{1:0=2d}:{2:0=2d}'.format(((d.seconds/3600) + d.days*24), ((d.seconds//60) % 60), (d.seconds % 60))

            # Update event timer
            self.counter_event.setText(event_timer)

    def task_parser(self, layer):
        event_dict = {}
        for feature in layer.getFeatures():
            # attrs is a list. It contains all the attribute values of this feature
            attrs = feature.attributes()
            event_dict[attrs[0]] = {'timed': attrs[1], 'title': attrs[2], 'about': attrs[3], 'group': attrs[4],
                                    'missing': attrs[5], 'priority': attrs[6], 'position': feature.geometry().asPoint()}
        return event_dict

    def check_events(self):
        self.task_list.show()

    def close_check_events(self):
        self.task_list.hide()

    def close_about_event(self):
        self.about_task.hide()
        # No event is selected anymore
        self.selected_event = None
        # Reset event timer
        self.counter_event.setText("--:--:--")
        self.task_list.show()

    def login_correct(self):
        # Hide login layer
        self.pass_popup.hide()

        # Show next layer
        self.wth_popup.show()
        getattr(self.wth_popup, "raise")()  #getattr(self.pass_popup, "lower")()  # Might be the opposite
        print "done"
