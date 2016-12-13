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
        email                : j.a.lopesgil@tudelft.nl
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
 This script initializes the plugin, making it known to QGIS.
"""


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load SpatialDecision class from file SpatialDecision.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .wth_main import Willing_to_Help
    return Willing_to_Help(iface)
