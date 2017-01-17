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

from PyQt4 import QtCore, uic
from PyQt4.QtGui import QWidget, QLabel, QHBoxLayout, QVBoxLayout, QDockWidget, QPixmap, QPushButton, QListWidgetItem, \
    QGridLayout
from qgis.core import *
from qgis.networkanalysis import *
from qgis.gui import *
import processing
from datetime import datetime, timedelta
import os

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

        # Position of the new event
        self.new_event_pos = []

        # Create a boolean variable to hold the state of "add a new event" procedure (Default = False)
        self.adding_new_event = False

        # Bind mouse click to canvas for adding new events
        self.map_canvas.mouseDoubleClickEvent = self.place_new_event

        # Bind buttons to specific path finding methods
        self.registerEvent_btn.clicked.connect(self.event_registration)

        self.menu_settings_btn.clicked.connect(self.show_user_panel)
        self.menu_group_btn.clicked.connect(self.show_group_panel)
        self.skills_list_back_btn.clicked.connect(self.hide_skills_panel)
        self.tools_list_back_btn.clicked.connect(self.hide_tools_panel)
        self.arrived_popup_back_btn.clicked.connect(self.arrived_popup.hide)
        self.user_panel_back_btn.clicked.connect(self.user_panel.hide)
        self.group_list_back_btn.clicked.connect(self.group_menu.hide)
        self.save_new_skills.clicked.connect(self.update_user_skills)
        # Toggle transparency of the shapefile showing the rest of the group
        self.toggle_show_members.clicked.connect(self.toggle_show_group)

        self.pushButton_yes.clicked.connect(self.will_to_help)
        self.pass_check_btn.clicked.connect(self.login_correct)

        self.menu_layers_btn.clicked.connect(self.check_events)
        self.task_list_back_btn.clicked.connect(self.close_check_events)
        self.about_event_back_btn.clicked.connect(self.close_about_event)
        self.register_event_back_btn.clicked.connect(self.close_register_event)
        self.register_event.clicked.connect(self.register_event_init)

        self.my_skills_btn.clicked.connect(self.show_skills_panel)
        self.my_tools_btn.clicked.connect(self.show_tools_panel)

        # Hide none init layers
        self.top_bar.hide()
        self.wth_popup.hide()
        self.task_list.hide()
        self.about_task.hide()
        self.register_task.hide()
        self.skills_list.hide()
        self.group_menu.hide()
        self.tools_list.hide()
        self.arrived_popup.hide()
        self.user_panel.hide()

        # Build a dictionary to handle the layer toggles
        self.layer_toggler = {"task_list": self.task_list, "about_task": self.about_task,
                              "register_task": self.close_register_event, "group_menu": self.group_menu,
                              "skills_list": self.skills_list, "tools_list": self.tools_list,
                              "arrived_popup": self.arrived_popup, "user_panel": self.user_panel}

        # Reference to the currently selected event
        self.selected_event = None

        # Reference to the ID of the event, to which user is currently registered.
        self.joined_event = None

        # A list to hold the layers that will be projected live
        self.added_canvaslayers = []

        # Dictionary of active shapefiles displayed
        self.active_shpfiles = {}

        # Define a dictionary to refer to each different user as a distinct feature object of a shapefile
        self.user_features = {}

        # Prepare system data dictionaries
        self.skills = {}
        self.tools = {}

        # Load System Data and convert them into Dictionaries.
        self.load_system_data()

        # Set user walking init state
        self.user_walking = False

        # User positioned path to joined event
        self.user_pos_path = []

        # Set joined event position as point
        self.joined_event_pos = None

        # Build icons dictionaries
        self.event_icons = {1: "EventPriority1.png", 2: "EventPriority2.png", 3: "EventPriority3.png"}

        # Show init layer
        getattr(self.pass_popup, "raise")()

    def protected_init(self):
        # Load specific classes of layers
        self.load_shapefiles()

        # Convert tasks into a dictionary
        self.task_dict = self.task_parser(self.active_shpfiles["tasks"][0])

        # Set user position as point
        self.user_pos = [feat for feat in self.active_shpfiles["user_logged"][0].getFeatures()][0].geometry().asPoint()

        # Refresh extent to user position
        self.refresh_extent("user_pos")

        # Refresh user tools list
        self.tools_list_loader()

        name = self.active_shpfiles["user_logged"][0].getFeatures().next()["first_name"] + " " + \
               self.active_shpfiles["user_logged"][0].getFeatures().next()["last_name"]

        # Refresh name
        self.user_name.setText(name)

    def place_new_event(self, *args):
        # If user is in the "adding a new event" section, proceed.
        if self.adding_new_event:

            # If group layer has been created in the past, delete it to prevent conflicts.
            if "group_pos" in self.active_shpfiles:
                QgsMapLayerRegistry.instance().removeMapLayer(self.active_shpfiles["group_pos"][0])

                # Delete the corresponding key from the active shapefiles dictionary
                del self.active_shpfiles["group_pos"]

                self.added_canvaslayers = [self.active_shpfiles[x][1] for x in [
                    "user_logged", "tasks", "road_network", "basemap", "ext_basemap"]]

                # provide set of layers for display on the map canvas
                self.map_canvas.setLayerSet(self.added_canvaslayers)

            # Get the raw extent of the map
            points = str(self.map_canvas.extent().toString()).split(":")
            point1 = points[0].split(",")
            point2 = points[1].split(",")

            # Get the minimum and the maximum extents of x and y of the map
            x_pos_min, x_pos_max = sorted([float(point1[0]), float(point2[0])])
            y_pos_min, y_pos_max = sorted([float(point1[1]), float(point2[1])])

            # Translate mouse position based on the canvas size (342x608)
            translated_x = x_pos_min + ((args[0].pos().x() * (x_pos_max - x_pos_min))/342.)
            translated_y = y_pos_max - ((args[0].pos().y() * (y_pos_max - y_pos_min))/608.)

            # Use road_network as the ref system.
            ref_layer = self.active_shpfiles["road_network"][0]

            # Generate a temp vector layer, of a point (that will have the translated coordinates).
            vl = QgsVectorLayer('%s?crs=EPSG:%s' % ('Point', ref_layer.crs().postgisSrid()), 'tmpPoint', "memory")

            # Make the temp point invisible
            symbol = QgsMarkerSymbolV2.createSimple({'size': '0'})
            vl.rendererV2().setSymbol(symbol)

            # Add the layer to the registry to be accessible by the processing
            QgsMapLayerRegistry.instance().addMapLayer(vl)

            pr = vl.dataProvider()

            # Add the feature point
            fet = QgsFeature()
            fet.setGeometry(QgsGeometry.fromPoint(QgsPoint(translated_x, translated_y)))

            # Set the position of the point based on the translated coordinates (point not on the road network)
            pr.addFeatures([fet])

            # Find the line segment (road) closer to the temp point layer. The algorithm runs hidden
            hub_point = processing.runalg('qgis:distancetonearesthub', vl, self.active_shpfiles["road_network"][0],
                                          "sid", 0, 0, None)

            # Get the sid of the line segment (road), found above.
            layer = QgsVectorLayer(hub_point['OUTPUT'], "hub_point", "ogr")

            # Remove the temp point layer to avoid conflicts with future 'qgis:distancetonearesthub' algorithm executions
            QgsMapLayerRegistry.instance().removeMapLayer(vl)

            # Create reference to the hub id of the road
            hub = [feat for feat in layer.getFeatures()][0]['HubName']

            # Get the line of the above sid by creating a filtered selection
            exp = QgsExpression("sid = " + str(hub))
            request = QgsFeatureRequest(exp)

            seg = [feat for feat in self.active_shpfiles["road_network"][0].getFeatures(request)][0].geometry().asPolyline()

            # Calculate closest point (from point) to line segment (road)
            geo_point = self.point_segment_intersect(seg, (translated_x, translated_y))

            # Add the new event to the registry
            QgsMapLayerRegistry.instance().addMapLayer(layer)

            # Clear the previously placed new_event (if there is one) from the map
            self.clear_last_new_event()

            # Snap new event point onto road network. Update point's geometry
            geom = QgsGeometry.fromPoint(QgsPoint(*geo_point))
            layer.dataProvider().changeGeometryValues({0: geom})

            # Add the layer to the dictionary
            self.active_shpfiles["new_event"] = [layer, QgsMapCanvasLayer(layer)]

            if "joined_event" in self.active_shpfiles:
                self.added_canvaslayers = [self.active_shpfiles[x][1] for x in ["user_logged", "tasks", "joined_event",
                                                                                "new_event", "road_network", "basemap", "ext_basemap"]]
            else:
                self.added_canvaslayers = [self.active_shpfiles[x][1] for x in
                                           ["user_logged", "tasks", "new_event", "road_network", "basemap", "ext_basemap"]]

            # provide set of layers for display on the map canvas
            self.map_canvas.setLayerSet(self.added_canvaslayers)

            # Set the flag of the new_event's registration button, to "Ready"
            self.register_event.setStyleSheet("QPushButton#register_event:hover {background-image: url(:/graphics/thin_button_background_correct.png);}")

    def clear_last_new_event(self):
        # If we have placed a "new event" on the map..
        if "new_event" in self.active_shpfiles:
            # Remove the previous new event to prevent multiple layer stacking
            QgsMapLayerRegistry.instance().removeMapLayer(self.active_shpfiles["new_event"][0])

            # Delete the layer from the dictionary
            del self.active_shpfiles["new_event"]

            # Re-render the road network (along with everything else)
            self.active_shpfiles["road_network"][0].triggerRepaint()

    # Calculate closest point (from point) to line segment
    def point_segment_intersect(self, seg, p):
        x1, y1 = seg[0]
        x2, y2 = seg[1]
        x3, y3 = p
        px = x2 - x1
        py = y2 - y1

        u = ((x3 - x1) * px + (y3 - y1) * py) / float(px * px + py * py)

        if u > 1:
            u = 1
        elif u < 0:
            u = 0

        x = x1 + u * px
        y = y1 + u * py

        return x, y

    def event_registration(self):
        # Set the flag of the new_event's registration button, to "Not Ready"
        self.register_event.setStyleSheet(
            "QPushButton#register_event:hover {background-image: url(:/graphics/thin_button_background_false.png);}")

        # Set the "adding a new event" state to True
        self.adding_new_event = True

        self.about_task.hide()
        self.task_list.hide()
        # Deactivate navigation
        if self.locate_me.isChecked():
            self.locate_me.toggle()

        # Keep only current layer
        self.layers_to_keep(["register_task"])

        self.register_task.show()

    def find_nearest_path(self):
        # Use road_network as the ref system.
        ref_layer = self.active_shpfiles["road_network"][0]
        # get the points to be used as origin and destination
        source_points = [self.user_pos, self.joined_event_pos]
        # build the graph including these points
        director = QgsLineVectorLayerDirector(ref_layer, -1, '', '', '', 3)
        properter = QgsDistanceArcProperter()
        director.addProperter(properter)
        builder = QgsGraphBuilder(ref_layer.crs())
        self.tied_points = director.makeGraph(builder, source_points)
        self.graph = builder.graph()
        # calculate the shortest path for the given origin and destination
        path = self.calculateRouteDijkstra(self.graph, self.tied_points[0], self.tied_points[1])
        self.draw_route(path, ref_layer)

    def draw_route(self, path, ref_lay):
        if not "joined_event" in self.active_shpfiles:
            vlayer = QgsVectorLayer('%s?crs=EPSG:%s' % ('LINESTRING', ref_lay.crs().postgisSrid()), 'Routes', "memory")

            # Set the symbology
            vlayer.loadNamedStyle( os.path.dirname(os.path.abspath(__file__)) + "/DB/shapefile_layers/user_path.qml")

            provider = vlayer.dataProvider()

            QgsMapLayerRegistry.instance().addMapLayer(vlayer)
        else:
            provider = self.active_shpfiles["joined_event"][0].dataProvider()
            features = [f for f in self.active_shpfiles["joined_event"][0].getFeatures()]
            provider.deleteFeatures([features[0].id()])

        # insert route line
        fet = QgsFeature()
        fet.setGeometry(QgsGeometry.fromPolyline(path))

        provider.addFeatures([fet])
        provider.updateExtents()

        x_min, x_max = sorted((self.joined_event_pos[0], self.user_pos[0]))
        y_min, y_max = sorted((self.joined_event_pos[1], self.user_pos[1]))
        extent = QgsRectangle(x_min-60, y_min-60, x_max+60, y_max+300)
        self.map_canvas.setExtent(extent)

        res = processing.runalg("qgis:createpointsalonglines", 'Routes', 7, 0, 0, None)

        # Update user positioned path to joined event
        layer = QgsVectorLayer(res['output'], "points_path", "ogr")
        self.user_pos_path = [feature.geometry().asPoint() for feature in layer.getFeatures()]
        self.user_pos_path.reverse()

        if "joined_event" not in self.active_shpfiles:
            # Add the layer to the dictionary
            self.active_shpfiles["joined_event"] = [vlayer, QgsMapCanvasLayer(vlayer)]

            self.added_canvaslayers = [self.active_shpfiles[x][1] for x in [
                "user_logged", "group_pos", "tasks", "joined_event", "road_network", "basemap", "ext_basemap"]]

            # provide set of layers for display on the map canvas
            self.map_canvas.setLayerSet(self.added_canvaslayers)

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

        # Container Widget
        event_widget = QWidget()
        event_widget.setStyleSheet("QWidget{background: transparent}")

        #Layout of Container Widget
        layout = QVBoxLayout(self)
        for event, attr in self.task_dict.iteritems():
            if attr['active'] == 1:
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

                # Generate the dynamic button widget
                dynamic_wid = self.event_button_generator(event, attr)

                event_text_layout.addWidget(dynamic_wid)

                # Get the corresponding list of tools
                str_lst = attr["tools"][1:-1].split(", ")

                # This check is to make sure the list is not empty, thus have a single space inside
                if str_lst != ['']:
                    int_tools_list = map(int, str_lst)
                else:
                    int_tools_list = []

                # Get the tools
                tools_list = ', '.join([self.tools[x] for x in int_tools_list])

                if tools_list == "":
                    tools_list = "-"

                event_skills = QLabel(tools_list)
                event_skills.setStyleSheet("QLabel {font-family: Roboto; font-size: 11pt; color: white;}")
                event_skills.setMaximumWidth(220)
                event_text_layout.addWidget(event_skills)
                event_layout.addLayout(event_text_layout)

                # Calculate the type of group icon
                if self.task_dict[event]['ppl_needed'] == self.task_dict[event]['joined']:
                    members_state = "Group_Icon1.png"
                else:
                    members_state = "Group_Icon0.png"

                group_icon_path = os.path.dirname(os.path.abspath(__file__)) + "/graphics/" + members_state
                group_icon = QLabel()
                group_icon.setGeometry(0, 0, 34, 34)
                group_icon.setMinimumWidth(34)
                group_icon.setMaximumWidth(34)
                group_icon.setPixmap(QPixmap(group_icon_path))
                event_layout.addWidget(group_icon)
                layout.addLayout(event_layout)

        event_widget.setLayout(layout)
        self.events_scrollArea.setWidget(event_widget)

    def event_button_generator(self, task_id, attr):
        btn = QPushButton(attr["title"])

        # Change the background if user has joined already the event
        if self.joined_event == task_id:
            btn.setStyleSheet(
                "QPushButton {font-family: Impact; font-size: 17pt; color: rgb(245, 238, 49); text-align: left;}")
        else:
            btn.setStyleSheet("QPushButton {font-family: Impact; font-size: 17pt; color: white; text-align: left;}")
        btn.setMinimumHeight(35)
        btn.setMaximumWidth(220)
        btn.clicked.connect(lambda: self.check_about_event(task_id, attr))
        return btn

    def check_about_event(self, task_id, attr):
        # Reset event timer
        self.counter_event.setText("--:--:--")

        # Set current event id as the selected one
        self.selected_event = task_id

        # Calculate the type of group icon
        if self.task_dict[task_id]['ppl_needed'] == self.task_dict[task_id]['joined']:
            members_state = "Group_Icon1.png"
        else:
            members_state = "Group_Icon0.png"

        group_icon_path = os.path.dirname(os.path.abspath(__file__)) + "/graphics/" + members_state
        self.about_group_icon.setPixmap(QPixmap(group_icon_path))
        self.event_title.setText(attr["title"])

        # Calculate how many members missing
        self.group_missing_note.setText('Missing {} people for a full party.'.format(
            self.task_dict[task_id]['ppl_needed'] - self.task_dict[task_id]['joined']))
        self.group_missing_note.setStyleSheet(
            "QLabel {font-family: Roboto; font-size: 11pt; color: white; qproperty-alignment: AlignCenter AlignRight;}")
        about_text = "<html><b>This and this and that.</b</html><br><br>" + attr["about"]
        self.about_event_txt.setText(about_text)
        try:
            self.join_event.clicked.disconnect()
        except:
            pass

        # Update the Button text
        self.join_event.setText("Join")

        # Bind join button to the corresponding function
        self.join_event.clicked.connect(lambda: self.join_event_started(task_id))

        # Zoom onto the selected event
        self.refresh_extent(task_id)

        # Hide the event list footer
        self.task_list.hide()

        # Show the about information of the selected event
        self.about_task.show()

    def join_event_started(self, event_id):
        # Set the position of the event
        self.joined_event_pos = self.task_dict[event_id]["position"]

        # Set the ID of the event that user is currently registered to
        self.joined_event = event_id

        # Create the group layer
        self.generate_group_layer()

        self.find_nearest_path()
        self.about_task.hide()
        # No event is selected anymore
        self.selected_event = None
        # Reset event timer
        self.counter_event.setText("--:--:--")
        self.user_walking = True

    def load_shapefiles(self):

        # Get the complete user layer
        users_layer = QgsVectorLayer(os.path.dirname(os.path.abspath(__file__)) + "/DB/shapefile_layers/users.shp",
                                     "all_user", "ogr")

        # Load the Raster basemaps
        s = QtCore.QSettings()
        oldValidation = s.value("/Projections/defaultBehaviour")
        s.setValue("/Projections/defaultBehaviour", "useGlobal")

        # Create the raster basemap layer
        basemap_layer = QgsRasterLayer(os.path.dirname(os.path.abspath(__file__)) + "/DB/shapefile_layers/basemap.tiff", "Basemap")
        basemap_layer.setCrs(QgsCoordinateReferenceSystem(28992, QgsCoordinateReferenceSystem.EpsgCrsId))

        # Create the extent raster extent_basemap layer
        ext_basemap_layer = QgsRasterLayer(os.path.dirname(os.path.abspath(__file__)) + "/DB/shapefile_layers/extent_basemap.tiff", "Extent Basemap")
        ext_basemap_layer.setCrs(QgsCoordinateReferenceSystem(28992, QgsCoordinateReferenceSystem.EpsgCrsId))

        s.setValue("/Projections/defaultBehaviour", oldValidation)

        # Add the raster layer to the dictionary
        self.active_shpfiles["basemap"] = [basemap_layer, QgsMapCanvasLayer(basemap_layer)]

        # Add the extent raster layer to the dictionary
        self.active_shpfiles["ext_basemap"] = [ext_basemap_layer, QgsMapCanvasLayer(ext_basemap_layer)]

        # Add the extent raster layer to the registry
        QgsMapLayerRegistry.instance().addMapLayer(ext_basemap_layer)

        # Add the raster layer to the registry
        QgsMapLayerRegistry.instance().addMapLayer(basemap_layer)

        # Update the dictionary refering to each different user as a distinct feature object of a shapefile
        for feature in users_layer.getFeatures():
            self.user_features[feature['UseID']] = feature

        # Create a logged-in user specific vector user
        user_layer = QgsVectorLayer('%s?crs=EPSG:%s' % ('Point', users_layer.crs().postgisSrid()), 'user', "memory")

        prov = user_layer.dataProvider()

        # Generate the fields
        prov.addAttributes([field for field in users_layer.pendingFields()])

        # Tell the vector layer to fetch changes from the provider
        user_layer.updateFields()

        # Add the user feature into the provider/layer
        prov.addFeatures([self.user_features[self.user_id]])

        # Set the symbol for the layer
        symbol = QgsMarkerSymbolV2.createSimple({'size': '3'})
        user_layer.rendererV2().setSymbol(symbol)

        # Delete the feature of the logged in user. That user became a seperate vlayer.
        del self.user_features[self.user_id]

        # Add the layer to the dictionary of active shapefiles
        self.active_shpfiles["user_logged"] = [user_layer, QgsMapCanvasLayer(user_layer)]

        # add the layer to the registry
        QgsMapLayerRegistry.instance().addMapLayer(user_layer)

        # load the rest of the vector layers
        for layer_class in ["tasks", "road_network"]:
            # create vector layer object
            vlayer = QgsVectorLayer(os.path.dirname(os.path.abspath(__file__)) + "/DB/shapefile_layers/" +
                                    layer_class + ".shp", layer_class, "ogr")

            # Apply the theme
            if layer_class == "road_network":
                # Set the symbol
                transp_symbol = QgsLineSymbolV2.createSimple({'line_style': 'no'})
                vlayer.rendererV2().setSymbol(transp_symbol)

            # Add the layer to the dictionary
            self.active_shpfiles[layer_class] = [vlayer, QgsMapCanvasLayer(vlayer)]

            # add the layer to the registry
            QgsMapLayerRegistry.instance().addMapLayer(vlayer)

        # Set the symbology
        self.active_shpfiles["tasks"][0].loadNamedStyle(
            os.path.dirname(os.path.abspath(__file__)) + "/DB/shapefile_layers/tasks.qml")

        # Load the corresponding Shapefiles
        self.added_canvaslayers = [self.active_shpfiles[x][1] for x in [
            "user_logged", "tasks", "road_network", "basemap", "ext_basemap"]]

        # provide set of layers for display on the map canvas
        self.map_canvas.setLayerSet(self.added_canvaslayers)

    def refresh_extent(self, layer_to_load):
        if layer_to_load == "user_pos":
            extnt = QgsRectangle(self.user_pos[0]-197.9, self.user_pos[1]-255, self.user_pos[0]+195.1, self.user_pos[1]+295)
        else:
            event_pos = self.task_dict[layer_to_load]["position"]
            extnt = QgsRectangle(event_pos[0]-197.9, event_pos[1]-350, event_pos[0]+195.1, event_pos[1]+50)

        # Reset the extent
        self.map_canvas.setExtent(extnt)

        # Re-render the road network (along with everything else)
        self.active_shpfiles["road_network"][0].triggerRepaint()

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()
        self.timer.stop()

    def will_to_help(self):
        # Prepare the z-Indexes and show the init layers
        self.wth_popup.hide()
        self.top_bar.show()
        getattr(self.top_bar, "raise")()
        getattr(self.menu_group_btn, "raise")()
        getattr(self.menu_layers_btn, "raise")()
        getattr(self.locate_me, "raise")()
        self.menu_group_btn.show()
        self.menu_layers_btn.show()
        self.locate_me.show()
        getattr(self.exp_score_main, "raise")()
        getattr(self.skills_list, "raise")()
        getattr(self.tools_list, "raise")()
        getattr(self.arrived_popup, "raise")()

    def refresher(self):
        # Append to time fixed seconds
        self.seconds_passed += 4
        # Simulate new time
        self_simulated_time = datetime.today() + timedelta(0, self.seconds_passed)

        # If use has selected to view a specific event..
        if self.selected_event != None:
            # Event's end time
            e = datetime.strptime(self.task_dict[self.selected_event]["timed"], '%Y-%m-%d %H:%M:%S')

            # Time difference between simulated time and event's end time
            d = e - self_simulated_time
            event_timer = '{0:0=2d}:{1:0=2d}:{2:0=2d}'.format(
                ((d.seconds/3600) + d.days*24), ((d.seconds//60) % 60), (d.seconds % 60))

            # Update event timer
            self.counter_event.setText(event_timer)

        if self.user_walking or self.locate_me.isChecked():
            if self.user_walking:

                #Get the ID of the user feature
                fid = [feat for feat in self.active_shpfiles["user_logged"][0].getFeatures()][0].id()

                # Try to get new user position from the path queue
                try:
                    self.user_pos = self.user_pos_path.pop()
                    geom = QgsGeometry.fromPoint(QgsPoint(self.user_pos))
                    self.active_shpfiles["user_logged"][0].dataProvider().changeGeometryValues({fid: geom})
                except:
                    # User arrived to the event. Terminate path
                    self.user_walking = False

                    # Update the popup message
                    self.arrived_popup_label.setText("You arrived at the hotspot.\nRemember, there are {} people in\n"
                                                     "total registered to help.\n\nGOOD LUCK and STAY SAFE!".format(3))

                    # Hide every possibly activated layer, to make following popup the single object being showed

                    # Hide all layers except arrived_popup
                    self.layers_to_keep(["arrived_popup"])

                    # Show notice that user reached the event destination
                    self.arrived_popup.show()

                    # Remove the previous new event to prevent multiple layer stacking
                    QgsMapLayerRegistry.instance().removeMapLayer(self.active_shpfiles["joined_event"][0])

                    # Delete the layer from the dictionary
                    del self.active_shpfiles["joined_event"]

                    # Re-render the road network (along with everything else)
                    self.active_shpfiles["road_network"][0].triggerRepaint()

            if self.locate_me.isChecked():
                self.refresh_extent("user_pos")
            else:
                self.active_shpfiles["road_network"][0].triggerRepaint()

    def task_parser(self, layer):
        tsk_d = {}
        # Build a dynamic reference list for the indexes of the fields
        flds = [str(field.name()) for field in layer.pendingFields()]

        for feature in layer.getFeatures():
            # attrs is a list. It contains all the attribute values of this feature
            attrs = feature.attributes()
            tsk_d[attrs[0]] = {'timed': str(attrs[flds.index('timed')]), 'title': str(attrs[flds.index('title')]),
                               'about': str(attrs[flds.index('about')]), 'joined': attrs[flds.index('joined')],
                               'priority': attrs[flds.index('priority')], 'ppl_needed': attrs[flds.index('ppl_needed')],
                               'skills': str(attrs[flds.index('skills')]), 'tools': str(attrs[flds.index('tools')]),
                               'active': attrs[flds.index('active')], 'position': feature.geometry().asPoint()}
        return tsk_d

    def check_events(self):

        # Refresh event list
        self.refresh_event_list()

        self.layers_to_keep(["task_list"])
        self.task_list.show()

    def close_check_events(self):
        self.task_list.hide()

    def close_register_event(self):
        # Hide the new event's registration panel
        self.register_task.hide()

        # Set the "adding a new event" state to False because user is closing the corresponding panel.
        self.adding_new_event = False

        # Clear the previously placed new_event (if there is one) from the map
        self.clear_last_new_event()

    def register_event_init(self):
        # Check if user has placed a new event
        if "new_event" in self.active_shpfiles:
            new_event_layer = self.active_shpfiles["new_event"][0]
            task_layer = self.active_shpfiles["tasks"][0]
            pr = task_layer.dataProvider()

            # Get the number of features to use as the sid
            sid = int(task_layer.featureCount())

            # Get the geometry of the new event layer to use as the correct one
            new_event_pos_geom = [feature.geometry() for feature in new_event_layer.getFeatures()][0]

            # Add the feature point
            fet = QgsFeature()
            fet.setGeometry(new_event_pos_geom)

            # Prepare the data into a temporal dict, to fill the new event
            edit_event_attr_bank = {'timed': str(self.register_counter_event.text()), 'title': str(self.NameEdit.text()),
                                    'about': str(self.register_event_txt.toPlainText()), 'priority': 3, 'active': 1,
                                    'ppl_needed': int(self.register_about_group_icon.text()), 'joined': 0, 'sid': sid,
                                    'skills': str([x.data(1) for x in self.register_skills_needed.selectedItems()]),
                                    'tools': str([x.data(1) for x in self.register_tools_needed.selectedItems()])}

            # Get all field names (in a correct order), of the tasks layer
            fields = [str(field.name()) for field in self.active_shpfiles["tasks"][0].pendingFields()]

            attrs = []

            # Add in the correct order each attribute, based on the attr bank
            for field in fields:
                attrs.append(edit_event_attr_bank[field])

            # Store the new feature with its attributes. It will automatically updated on the task layer.
            fet.setAttributes(attrs)
            pr.addFeatures([fet])

            # Clear the previously placed new_event (if there is one) from the map
            self.clear_last_new_event()

            # Add the position to the previously created temporal dict
            edit_event_attr_bank['position'] = new_event_pos_geom.asPoint()

            # Remove the unusable "sid" key from the dictionary
            del edit_event_attr_bank['sid']

            # Refresh the dictionary based on the new event
            self.task_dict[sid] = edit_event_attr_bank

            # Refresh event list
            self.refresh_event_list()

            # Call the handler of the new_event's registration panel exit
            self.close_register_event()

    def close_about_event(self):
        self.about_task.hide()

        if self.selected_event is not None:
            self.task_list.show()

        # No event is selected anymore
        self.selected_event = None

        # Reset event timer
        self.counter_event.setText("--:--:--")

    def load_system_data(self):
        # Prepare data about skill attributes
        with open(os.path.dirname(os.path.abspath(__file__)) + "/DB/skills.db") as f:
            for line in f:
                pair = line.split(";")
                if pair[1][-1:] == "\n":
                    val = pair[1][:-1]
                else:
                    val = pair[1]

                self.skills[int(pair[0])] = val

                # Build one skills selection list for the new event registration screen and one for the user area.
                item = QListWidgetItem(val)
                item2 = QListWidgetItem(val)
                item.setData(1, int(pair[0]))
                item2.setData(1, int(pair[0]))
                self.register_skills_needed.addItem(item)
                self.skills_picklist.addItem(item2)

        # Prepare data about tool attributes
        with open(os.path.dirname(os.path.abspath(__file__)) + "/DB/tools.db") as f:
            for line in f:
                pair = line.split(";")
                if pair[1][-1:] == "\n":
                    val = pair[1][:-1]
                else:
                    val = pair[1]
                self.tools[int(pair[0])] = val

                # Build the selection list for tools, being available in the new event registration screen.
                item = QListWidgetItem(val)
                item.setData(1, int(pair[0]))
                self.register_tools_needed.addItem(item)

    def tools_list_loader(self):
        # Container Widget
        tools_widget_panel = QWidget()
        tools_widget_panel.setStyleSheet("QWidget{background: transparent}")

        #Layout of Container Widget
        tools_widget_grid = QGridLayout(self)

        # Create a counter to track the current iteration
        iteration_tracker = 1

        # Create a counter to track the current row
        row = 1

        for tool_id, name in self.tools.iteritems():

            tool_framebox = QVBoxLayout(self)

            # Place the icon that will be generated dynamically
            tool_framebox.addWidget(self.tools_checkbutton_generator(tool_id))

            # Make the name shorter in case needed.
            if len(name) > 11:
                name = name[:11]+".."

            tool_title = QLabel(name)
            tool_title.setStyleSheet("QLabel {font-family: Roboto; font-size: 9pt; color: white; qproperty-alignment: AlignCenter;}")
            tool_title.setMaximumWidth(81)

            # Place Title under the icon
            tool_framebox.addWidget(tool_title)

            # Make proper calculations for proper slot indexing
            col = iteration_tracker % 3
            if col == 0:
                col = 3
                tools_widget_grid.addLayout(tool_framebox, row, col)
                row += 1
            else:
                tools_widget_grid.addLayout(tool_framebox, row, col)

            #Update iteration trackers
            iteration_tracker += 1

        tools_widget_panel.setLayout(tools_widget_grid)
        self.tools_scrollArea.setWidget(tools_widget_panel)

    def tools_checkbutton_generator(self, tool_id):

        btn = QPushButton()
        name = "tool_btn_" + str(tool_id)
        btn.setObjectName(name)
        btn.setCheckable(True)

        # Get tools list (from string to int)
        int_tools_list = self.list_str2int("tools")

        # Check if user has this tool:
        if tool_id in int_tools_list:
            btn.setChecked(True)
        else:
            btn.setChecked(False)

        # Set the styling for each check_button
        btn.setStyleSheet(
            "QPushButton#" + name + " {background-image: url(:/graphics/tools/" + str(tool_id) + "_off.png);}\n\n" +
            "QPushButton#" + name + ":checked {background-image: url(:/graphics/tools/" + str(tool_id) + ".png);}")

        # Set the size of the button
        btn.setMinimumHeight(81)

        # Connect checkbox to list handler
        btn.toggled.connect(lambda: self.update_list("tools", tool_id, btn.isChecked()))

        return btn

    # Gets a list of strings and returns a list of integers
    def list_str2int(self, str_list):
        # Get the corresponding list
        str_lst = [feat for feat in self.active_shpfiles["user_logged"][0].getFeatures()][0][str_list][1:-1].split(", ")

        # This check is for the skills. We make sure the list is not empty, thus have a single space inside
        if str_lst != ['']:
            return map(int, str_lst)
        else:
            return []

    # Update the corresponding list based on the chosen id of the object
    def update_list(self, list_type, sid, state):
        # Get the feature (logged user)
        feat = [feat for feat in self.active_shpfiles["user_logged"][0].getFeatures()][0]

        # If check state is True, it means we are adding an object
        if state:
            old_list = feat[list_type][:-1]

            # If list did not have any objects, then just add a number without a comma
            if old_list == "[":
                # Add to the list the new object
                new_object_list = old_list + str(sid) + "]"

            # Else, add the comma because list was not empty
            else:
                # Add to the list the new object
                new_object_list = old_list + ", " + str(sid) + "]"

        # If not, then we should remove the object from the list
        else:
            # Get tools list (from string to int)
            int_tools_list = self.list_str2int(list_type)

            # Remove the object id
            int_tools_list.remove(sid)

            # Convert the list of integers back to list of strings
            new_object_list = str(int_tools_list)

        # Update the list
        with edit(self.active_shpfiles["user_logged"][0]):
            f = self.active_shpfiles["user_logged"][0].getFeatures().next()
            f[list_type] = new_object_list
            self.active_shpfiles["user_logged"][0].updateFeature(f)

    def hide_skills_panel(self):

        self.skills_list.hide()

    def hide_tools_panel(self):

        self.tools_list.hide()

    def show_skills_panel(self):
        # Get skills list (from string to int)
        int_skills_list = self.list_str2int("skills")

        # Everytime screen loads, reset the skill selections, based on user's skills.
        for skill in range(self.skills_picklist.count()):
            if self.skills_picklist.item(skill).data(1) in int_skills_list:
                self.skills_picklist.item(skill).setSelected(True)
            else:
                self.skills_picklist.item(skill).setSelected(False)

        self.skills_list.show()

    def update_user_skills(self):
        new_user_skills = [skill.data(1) for skill in self.skills_picklist.selectedIndexes()]

        # Get the logged user (feature) and update the skill-list
        with edit(self.active_shpfiles["user_logged"][0]):
            f = self.active_shpfiles["user_logged"][0].getFeatures().next()
            f["skills"] = str(new_user_skills)
            self.active_shpfiles["user_logged"][0].updateFeature(f)

        # Hide the skills panel after saving
        self.skills_list.hide()

    def show_tools_panel(self):

        self.tools_list.show()

    def show_group_panel(self):

        if self.joined_event is not None:

            # No event is selected anymore
            self.selected_event = None

            # If group_pos does not exist.. Create the group layer
            if "group_pos" not in self.active_shpfiles:
                self.generate_group_layer()

            # Prepare list with group names
            self.get_group_members()

            self.layers_to_keep(["group_menu"])
            self.group_menu.show()

            # Prepare the info of the joined event
            self.prepare_about_joined_task()

            # Show the about information of the selected event
            self.about_task.show()
        else:
            self.arrived_popup.show()
            # Update the popup message

            # Set the warning message
            self.arrived_popup_label.setText("\n{}, first register\nyourself to an event!".format(
                self.active_shpfiles["user_logged"][0].getFeatures().next()["first_name"]))

    def generate_group_layer(self):
        # Use road_network as the ref system.
        ref_layer = self.active_shpfiles["road_network"][0]

        # If group layer has been created in the past, try deleting it.
        if "group_pos" in self.active_shpfiles:
            try:
                # Remove the previous new event to prevent multiple layer stacking
                QgsMapLayerRegistry.instance().removeMapLayer(self.active_shpfiles["group_pos"][0])
            except:
                pass

        # Generate a temp vector layer, of a point (that will have the translated coordinates).
        group_layer = QgsVectorLayer('%s?crs=EPSG:%s' % ('Point', ref_layer.crs().postgisSrid()), 'GroupPOS', "memory")

        # Set the layer's provider
        pr = group_layer.dataProvider()

        # Generate the fields, based on the fields of the user layer
        pr.addAttributes([field for field in self.active_shpfiles["user_logged"][0].pendingFields()])

        # Tell the vector layer to fetch changes from the provider
        group_layer.updateFields()

        # For each user
        for user, attrs in self.user_features.iteritems():
            # If user has also joined the event..
            if attrs["joined_tsk"] == self.joined_event:

                # Add the user feature on the layer
                pr.addFeatures([attrs])
                pr.updateExtents()

        # Add the layer to the dictionary
        self.active_shpfiles["group_pos"] = [group_layer, QgsMapCanvasLayer(group_layer)]

        # Toggle show members button on
        self.toggle_show_members.setChecked(True)

        # add the layer to the registry
        QgsMapLayerRegistry.instance().addMapLayer(group_layer)

        # Load the corresponding Shapefiles
        if "joined_event" in self.active_shpfiles:
            self.added_canvaslayers = [self.active_shpfiles[x][1] for x in [
                "user_logged", "group_pos", "tasks", "joined_event", "road_network", "basemap", "ext_basemap"]]
        else:
            self.added_canvaslayers = [self.active_shpfiles[x][1] for x in [
                "user_logged", "group_pos", "tasks", "road_network", "basemap", "ext_basemap"]]

        # provide set of layers for display on the map canvas
        self.map_canvas.setLayerSet(self.added_canvaslayers)

        # Set the symbology
        group_layer.loadNamedStyle(os.path.dirname(os.path.abspath(__file__)) + "/DB/shapefile_layers/group_layer.qml")

    def get_group_members(self):
        # Remove all old entries
        self.group_list.clear()

        # For each user
        for user, attrs in self.user_features.iteritems():
            # If user has also joined the event..
            if attrs["joined_tsk"] == self.joined_event:
                # Add each member in the list.
                self.group_list.addItem(QListWidgetItem("{} {}".format(attrs["first_name"], attrs["last_name"])))

    def prepare_about_joined_task(self):
        # Calculate the type of group icon
        if self.task_dict[self.joined_event]['ppl_needed'] == self.task_dict[self.joined_event]['joined']:
            members_state = "Group_Icon1.png"
        else:
            members_state = "Group_Icon0.png"

        group_icon_path = os.path.dirname(os.path.abspath(__file__)) + "/graphics/" + members_state
        self.about_group_icon.setPixmap(QPixmap(group_icon_path))
        self.event_title.setText(self.task_dict[self.joined_event]["title"])

        # Calculate how many members missing
        self.group_missing_note.setText('Missing {} people for a full party.'.format(
            self.task_dict[self.joined_event]['ppl_needed'] - self.task_dict[self.joined_event]['joined']))
        self.group_missing_note.setStyleSheet(
            "QLabel {font-family: Roboto; font-size: 11pt; color: white; qproperty-alignment: AlignCenter AlignRight;}")
        about_text = "<html><b>This and this and that.</b</html><br><br>" + self.task_dict[self.joined_event]["about"]
        self.about_event_txt.setText(about_text)

        # Update the Button text
        self.join_event.setText("DONE!")

        # Update the Button text
        self.counter_event.setText("Quit")

        # This button is used in many cases. Disconnect all previous connections.
        try:
            self.join_event.clicked.disconnect()
        except:
            pass

        # Bind join button to the corresponding function
        self.join_event.clicked.connect(self.joined_event_done)

    def joined_event_done(self):
        # Set user walking init state
        self.user_walking = False

        # If user was ontop of a path..
        if "joined_event" in self.active_shpfiles:
            # Remove the "joined_event" layer
            QgsMapLayerRegistry.instance().removeMapLayer(self.active_shpfiles["joined_event"][0])

            # Delete the corresponding key from the active shapefiles dictionary
            del self.active_shpfiles["joined_event"]

        # Remove the "group_pos" layer
        QgsMapLayerRegistry.instance().removeMapLayer(self.active_shpfiles["group_pos"][0])

        # Delete the corresponding key from the active shapefiles dictionary
        del self.active_shpfiles["group_pos"]

        self.added_canvaslayers = [self.active_shpfiles[x][1] for x in [
            "user_logged", "tasks", "road_network", "basemap", "ext_basemap"]]

        # provide set of layers for display on the map canvas
        self.map_canvas.setLayerSet(self.added_canvaslayers)

        # Get user's history data
        hist = self.active_shpfiles["user_logged"][0].getFeatures().next()["tasks_name"][:-1]
        hist_numb = self.active_shpfiles["user_logged"][0].getFeatures().next()["tasks_done"]

        # If user has no history record
        if len(hist) == 1:
            hist = hist + self.task_dict[self.joined_event]["title"] + "]"
        else:
            hist = hist + ";;" + self.task_dict[self.joined_event]["title"] + "]"

        # Update user's history
        with edit(self.active_shpfiles["user_logged"][0]):
            f = self.active_shpfiles["user_logged"][0].getFeatures().next()
            f["tasks_name"] = hist
            f["tasks_done"] = hist_numb + 1
            self.active_shpfiles["user_logged"][0].updateFeature(f)

        for feature in self.active_shpfiles["tasks"][0].getFeatures():
            # Get the corresponding task
            if feature["sid"] == self.joined_event:
                # Update task lists (both dictionary and layer) to hide the event
                with edit(self.active_shpfiles["tasks"][0]):
                    feature["active"] = 0
                    self.task_dict[self.joined_event]["active"] = 0
                    self.active_shpfiles["tasks"][0].updateFeature(feature)

        # User is not participating in any event anymore
        self.joined_event = None

        self.layers_to_keep(["user_panel"])
        self.show_user_panel()

    def toggle_show_group(self):
        if self.toggle_show_members.isChecked():
            # Load the corresponding Shapefiles
            if "joined_event" in self.active_shpfiles:
                self.added_canvaslayers = [self.active_shpfiles[x][1] for x in [
                    "user_logged", "group_pos", "tasks", "joined_event", "road_network", "basemap", "ext_basemap"]]
            else:
                self.added_canvaslayers = [self.active_shpfiles[x][1] for x in [
                    "user_logged", "group_pos", "tasks", "road_network", "basemap", "ext_basemap"]]
        else:
            if "joined_event" in self.active_shpfiles:
                self.added_canvaslayers = [self.active_shpfiles[x][1] for x in [
                    "user_logged", "tasks", "joined_event", "road_network", "basemap", "ext_basemap"]]
            else:
                self.added_canvaslayers = [self.active_shpfiles[x][1] for x in [
                    "user_logged", "tasks", "road_network", "basemap", "ext_basemap"]]

        # provide set of layers for display on the map canvas
        self.map_canvas.setLayerSet(self.added_canvaslayers)

    def layers_to_keep(self, keep_layers):
        # For every layer in the toggler dictionary
        for layer in self.layer_toggler:
            # Hide the specific layer based on keep_layers list
            if layer not in keep_layers and layer == "register_task":
                self.layer_toggler[layer]()
            elif layer not in keep_layers:
                self.layer_toggler[layer].hide()

    def show_user_panel(self):

        # Hide first all other panels..
        self.layers_to_keep("user_panel")

        # Get the original number of user's completed tasks
        exp = self.active_shpfiles["user_logged"][0].getFeatures().next()["tasks_done"]

        # Set the exp number
        self.exp_score_main.setText("\n\n{}".format(exp))

        # Do this to handle the low number of events we currently have for the demo
        exp *= 10
        if exp > 99:
            exp = 99

        # Calculate the color of user exp
        r = ((255 * exp) / 100) % 255
        g = ((255 * (100 - exp)) / 100) % 255
        b = 0

        rgb = "{}, {}, {}".format(r, g, b)

        # Set the color based on user's experience
        self.exp_score_back.setStyleSheet(
            "QLabel {background-color: rgb(" + rgb + "); background-position: top left; border: none;}")

        # Remove all old entries
        self.event_history_list.clear()

        hist = self.active_shpfiles["user_logged"][0].getFeatures().next()["tasks_name"][1:-1].split(";;")

        # For each user..
        for idx, event in enumerate(hist):
            # Add each member in the list.
            self.event_history_list.addItem(QListWidgetItem("{}. {}".format(idx+1, event)))

        # Show the panel
        self.user_panel.show()

    def login_correct(self):
        # Set the user based on the credentials
        self.user_id = int(self.user_selection.text())

        # Proceed to the protected init (User has logged in successfully)
        self.protected_init()

        # Hide login layer
        self.pass_popup.hide()

        # Show next layer
        self.wth_popup.show()
        getattr(self.wth_popup, "raise")()
