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
from PyQt4.QtGui import QWidget, QLabel, QHBoxLayout, QVBoxLayout, QDockWidget, QPixmap, QPushButton, QListWidgetItem, QCursor
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
        #self.menu_settings_btn.clicked.connect()  # Todo user edit

        # Reference to the currently selected event
        self.selected_event = None

        # Set Button connections
        self.pushButton_yes.clicked.connect(self.will_to_help)
        self.pass_check_btn.clicked.connect(self.login_correct)

        self.menu_layers_btn.clicked.connect(self.check_events)
        self.task_list_back_btn.clicked.connect(self.close_check_events)
        self.about_event_back_btn.clicked.connect(self.close_about_event)
        self.register_event_back_btn.clicked.connect(self.close_register_event)
        self.register_event.clicked.connect(self.register_event_init)

        # Hide none init layers
        self.top_bar.hide()
        self.wth_popup.hide()
        self.task_list.hide()
        self.about_task.hide()
        self.register_task.hide()

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

        # Refresh event list
        self.refresh_event_list()

    def place_new_event(self, *args):
        # If user is in the "adding a new event" section, proceed.
        if self.adding_new_event:
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
            #fet.setAttributes(["NewEvent", 2, 0.3])
            pr.addFeatures([fet])

            # update layer’s extent when new features have been added
            # because change of extent in provider is not propagated to the layer
            #vl.updateExtents() # Todo do I need?

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

            # Make the temp point invisible
            #symb = QgsMarkerSymbolV2.createSimple({'size': '2'})
            #layer.rendererV2().setSymbol(symb)

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
                                                                                "new_event", "road_network"]]
            else:
                self.added_canvaslayers = [self.active_shpfiles[x][1] for x in
                                           ["user_logged", "tasks", "new_event", "road_network"]]

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

            # Set the symbol
            symbol = QgsLineSymbolV2.createSimple({'line_width': '1'})
            vlayer.rendererV2().setSymbol(symbol)

            provider = vlayer.dataProvider()

            QgsMapLayerRegistry.instance().addMapLayer(vlayer)
        else:
            provider = self.active_shpfiles["joined_event"][0].dataProvider()
            features = [f for f in self.active_shpfiles["joined_event"][0].getFeatures()]
            provider.deleteFeatures([features[0].id()])

        # insert route line
        fet = QgsFeature()
        fet.setGeometry(QgsGeometry.fromPolyline(path))
        #fet.setAttributes(['Fastest Route'])
        provider.addFeatures([fet])
        provider.updateExtents()

        x_min, x_max = sorted((self.joined_event_pos[0], self.user_pos[0]))
        y_min, y_max = sorted((self.joined_event_pos[1], self.user_pos[1]))
        extent = QgsRectangle(x_min-60, y_min-60, x_max+60, y_max+300)
        self.map_canvas.setExtent(extent)

        res = processing.runalg("qgis:createpointsalonglines", 'Routes', 7, 0, 0, None)
        #self.iface.addVectorLayer(res['output'], 'my points', 'ogr')

        # Update user positioned path to joined event
        layer = QgsVectorLayer(res['output'], "points_path", "ogr")
        self.user_pos_path = [feature.geometry().asPoint() for feature in layer.getFeatures()]
        self.user_pos_path.reverse()

        if "joined_event" not in self.active_shpfiles:
            # Add the layer to the dictionary
            self.active_shpfiles["joined_event"] = [vlayer, QgsMapCanvasLayer(vlayer)]

            self.added_canvaslayers = [self.active_shpfiles[x][1] for x in [
                "user_logged", "tasks", "joined_event", "road_network"]]

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
        btn.setStyleSheet("QPushButton {font-family: Impact; font-size: 17pt; color: white; text-align: left;}")
        btn.setMinimumHeight(35)
        btn.setMaximumWidth(220)
        btn.clicked.connect(lambda: self.check_about_event(task_id, attr))
        return btn

    def check_about_event(self, task_id, attr):
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
        self.user_walking = True

    def load_shapefiles(self):

        # Get the complete user layer
        users_layer = QgsVectorLayer(os.path.dirname(os.path.abspath(__file__)) + "/DB/shapefile_layers/users.shp",
                                     "all_user", "ogr")

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

        # Make the temp point invisible
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

            # Add the layer to the dictionary
            self.active_shpfiles[layer_class] = [vlayer, QgsMapCanvasLayer(vlayer)]

            # add the layer to the registry
            QgsMapLayerRegistry.instance().addMapLayer(vlayer)

        # Load the corresponding Shapefiles
        self.added_canvaslayers = [self.active_shpfiles[x][1] for x in ["user_logged", "tasks", "road_network"]]

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
        self.wth_popup.hide()
        self.top_bar.show()
        getattr(self.top_bar, "raise")()
        getattr(self.menu_group_btn, "raise")()
        getattr(self.menu_layers_btn, "raise")()
        getattr(self.locate_me, "raise")()
        self.menu_group_btn.show()
        self.menu_layers_btn.show()
        self.locate_me.show()
        print "Lets get down to business"

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
            event_timer = '{0:0=2d}:{1:0=2d}:{2:0=2d}'.format(((d.seconds/3600) + d.days*24), ((d.seconds//60) % 60), (d.seconds % 60))

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
                               'position': feature.geometry().asPoint()}
        return tsk_d

    def check_events(self):
        self.task_list.show()
        # Call the handler of the new_event's registration panel exit
        self.close_register_event()
        self.about_task.hide()

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
                                    'about': str(self.register_event_txt.toPlainText()), 'priority': 3,
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

            # Redraw the widget on the canvas
            self.canvas.refresh()  # todo needed?

    def close_about_event(self):
        self.about_task.hide()
        # No event is selected anymore
        self.selected_event = None
        # Reset event timer
        self.counter_event.setText("--:--:--")
        self.task_list.show()

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

                # Build the selection list for skills, being available in the new event registration screen.
                item = QListWidgetItem(val)
                item.setData(1, int(pair[0]))
                self.register_skills_needed.addItem(item)

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
        print "done"
