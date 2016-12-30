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
import os
#from . import utility_functions as uf

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

        # Define the graph
        self.graph = QgsGraph()
        # Define the list of tied points
        self.tied_points = []

        # Development stage
        self.setNetworkButton.hide()
        self.shortestRouteButton.hide()
        self.clearRouteButton.hide()
        # Bind buttons to specific path finding methods
        #self.setNetworkButton.clicked.connect(self.buildNetwork)
        #self.shortestRouteButton.clicked.connect(self.calculateRoute)
        #self.clearRouteButton.clicked.connect(self.deleteRoutes)

        # Reference to the currently selected event
        self.selected_event = None

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

        # Dictionary of active shapefiles displayed
        self.active_shpfiles = {}

        # Load specific classes of layers
        self.load_shapefiles(["user_pos", "tasks", "road_network"])

        # Convert tasks into a dictionary
        self.task_dict = self.task_parser(self.active_shpfiles["tasks"][0])

        # Set user position as point
        self.user_pos = [feat for feat in self.active_shpfiles["user_pos"][0].getFeatures()][0].geometry().asPoint()

        # Set joined event position as point
        self.joined_event_pos = None
        self.joined_event_pos = self.task_dict[145524]["position"]  # TODO delete, this is only for testing

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

    def find_nearest_path(self):
        # Get road_network
        self.network_layer = self.active_shpfiles["road_network"][0]
        # get the points to be used as origin and destination
        source_points = [self.user_pos, self.joined_event_pos]
        # build the graph including these points
        director = QgsLineVectorLayerDirector(self.network_layer, -1, '', '', '', 3)
        properter = QgsDistanceArcProperter()
        director.addProperter(properter)
        builder = QgsGraphBuilder(self.network_layer.crs())
        self.tied_points = director.makeGraph(builder, source_points)
        self.graph = builder.graph()
        # calculate the shortest path for the given origin and destination
        path = self.calculateRouteDijkstra(self.graph, self.tied_points[0], self.tied_points[1])
        #print path
        self.draw_route(path)

    def draw_route(self, path):
        if not "joined_event" in self.active_shpfiles:
            vlayer = QgsVectorLayer('%s?crs=EPSG:%s' % ('LINESTRING', self.network_layer.crs().postgisSrid()), 'Routes', "memory")
            symbol = QgsLineSymbolV2.createSimple({'line_width': '1'})
            vlayer.rendererV2().setSymbol(symbol)
            #print vlayer.rendererV2().symbol().symbolLayers()[0].properties()
            vlayer.startEditing()
            provider = vlayer.dataProvider()
            provider.addAttributes([QgsField('id', QtCore.QVariant.String)])
            vlayer.commitChanges()
            QgsMapLayerRegistry.instance().addMapLayer(vlayer)
        else:
            provider = self.active_shpfiles["joined_event"][0].dataProvider()
            features = [f for f in self.active_shpfiles["joined_event"][0].getFeatures()]
            provider.deleteFeatures([features[0].id()])

        # insert route line
        fet = QgsFeature()
        fet.setGeometry(QgsGeometry.fromPolyline(path))
        fet.setAttributes(['Fastest Route'])
        provider.addFeatures([fet])
        provider.updateExtents()

        x_min, x_max = sorted((self.joined_event_pos[0], self.user_pos[0]))
        y_min, y_max = sorted((self.joined_event_pos[1], self.user_pos[1]))
        extent = QgsRectangle(x_min-60, y_min-60, x_max+60, y_max+250)

        self.map_canvas.setExtent(extent)

        if "joined_event" not in self.active_shpfiles:
            # Add the layer to the dictionary
            self.active_shpfiles["joined_event"] = [vlayer, QgsMapCanvasLayer(vlayer)]

            added_canvaslayers = [self.active_shpfiles[x][1] for x in ["user_pos", "tasks", "joined_event", "road_network"]]

            # provide set of layers for display on the map canvas
            self.map_canvas.setLayerSet(added_canvaslayers)

        # Re-render the road network (along with everything else)
        self.active_shpfiles["road_network"][0].triggerRepaint()

    def calculateRouteDijkstra(self, graph, from_point, to_point, impedance=0):
        points = []
        # analyse graph
        from_id = graph.findVertex(from_point)
        to_id = graph.findVertex(to_point)
        (tree, cost) = QgsGraphAnalyzer.dijkstra(graph, from_id, impedance)
        if tree[to_id] == -1:
            pass
        else:
            curPos = to_id
            while curPos != from_id:
                points.append(graph.vertex(graph.arc(tree[curPos]).inVertex()).point())
                curPos = graph.arc(tree[curPos]).outVertex()

            points.append(from_point)
            points.reverse()
        return points

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
        self.joined_event_pos = self.task_dict[event_id]["position"]
        self.find_nearest_path()
        self.about_task.hide()
        # No event is selected anymore
        self.selected_event = None
        # Reset event timer
        self.counter_event.setText("--:--:--")

    def load_shapefiles(self, shp_files):
        # load vector layers
        for layer_class in shp_files:
            # create vector layer object
            vlayer = QgsVectorLayer(os.path.dirname(os.path.abspath(__file__)) + "/DB/shapefile_layers/" +
                                    layer_class + ".shp", layer_class, "ogr")

            # Add the layer to the dictionary
            self.active_shpfiles[layer_class] = [vlayer, QgsMapCanvasLayer(vlayer)]

            # add the layer to the registry
            QgsMapLayerRegistry.instance().addMapLayer(vlayer)

        added_canvaslayers = [self.active_shpfiles[x][1] for x in shp_files]

        # provide set of layers for display on the map canvas
        self.map_canvas.setLayerSet(added_canvaslayers)

    def refresh_extent(self, layer_to_load):
        if layer_to_load == "user_pos":
            extnt = QgsRectangle(self.user_pos[0]-197.9, self.user_pos[1]-255, self.user_pos[0]+195.1, self.user_pos[1]+295)
        else:
            event_pos = self.task_dict[layer_to_load]["position"]
            extnt = QgsRectangle(event_pos[0]-197.9, event_pos[1]-350, event_pos[0]+195.1, event_pos[1]+50)
        # Reset the extent
        self.map_canvas.setExtent(extnt)
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
