# -*- coding: utf-8 -*-
"""
/***************************************************************************
 QRectangleCreator
                                 A QGIS plugin
 Plugin to create polygon
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2019-05-16
        git                  : https://github.com/abocianowski/QRectangleCreator
        copyright            : (C) 2019 by Adrian Bocianowski
        email                : adrian@bocianowski.com.pl
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
import functools
import logging
from dataclasses import field

from qgis.PyQt import uic
from qgis._core import QgsSettings

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

from qgis._gui import QgsMessageBar
try:
    import pydevd_pycharm

    pydevd_pycharm.settrace('localhost', port=53210, stdoutToServer=True, stderrToServer=True)
except Exception as e:
    logger.error(f"Error: {e}")
from .resources import *

from PyQt5.QtCore import QSettings, QTranslator, qVersion, QCoreApplication, QPoint, Qt
from PyQt5.QtGui import QIcon, QColor
from PyQt5.QtWidgets import QAction, QToolButton, QMenu, QLineEdit, QComboBox, QInputDialog

from PyQt5 import QtWidgets

from qgis.gui import QgsMapToolEmitPoint, QgsRubberBand, QgsMapCanvas, QgsVertexMarker
from qgis.core import QgsWkbTypes, QgsPoint, QgsGeometry, QgsPointXY, QgsPointLocator, QgsFeature, \
    QgsCoordinateTransform, QgsCoordinateReferenceSystem, QgsProject

import math
from pyproj import Proj, transform
import os


def try_catch(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Exception occurred in {func.__name__}: {e}", exc_info=True)
            # Optionally, you can re-raise the exception or handle it as needed
            # raise
            if len(args) > 0 and isinstance(args[0], (QRectangleCreator, StartDrawing)):
                args[0].iface.messageBar().pushCritical('QRectangle Creator: ', f'Error: {e}')

    return wrapper


class QRectangleCreator:
    def __init__(self, iface):

        self.mainButton = QToolButton()
        self.preset_size_dropdown = QComboBox()
        self.add_to_presets_button = QToolButton()
        self.remove_from_presets_button = QToolButton()
        self.config = {
        }
        self.load_settings()
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'qrectanglecreator_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        self.actions = []
        self.menu = self.tr(u'&QRectangleCreator')
        self.toolsToolbar = self.iface.addToolBar(u'QRectangle Creator')
        self.toolsToolbar.setObjectName(u'QRectangle Creator')
        self.settingsDlg = SettingsDialog()
        self.settingsDlg.width.valueChanged.connect(self.updateWidth)
        self.settingsDlg.height.valueChanged.connect(self.updateHeight)
        self.settingsDlg.angle.valueChanged.connect(self.updateAngle)
        self.first_start = None
        self.h_box = QLineEdit()
        self.w_box = QLineEdit()
        self.a_box = QLineEdit()
    @try_catch
    def updateWidth(self, width):
        _width = self.config['width']
        width = float(width)
        try:
            self.settingsChanged({'width': float(width)})
        except Exception as e:
            self.settingsChanged({'width': _width})
    @try_catch
    def updateHeight(self, height):
        _height = self.config['height']
        height = float(height)
        try:
            self.settingsChanged({'height': float(height)})
        except Exception as e:
            self.settingsChanged({'height': _height})
    @try_catch
    def updateAngle(self, angle):
        _angle = self.config['angle']
        angle = float(angle) % 360
        try:
            self.settingsChanged({'angle': float(angle)})
        except Exception as e:
            self.settingsChanged({'angle': _angle})


    def tr(self, message):
        return QCoreApplication.translate('QRectangleCreator', message)

    @try_catch
    def load_settings(self):
        settings = QgsSettings()
        settings.beginGroup('QRectangleCreator')
        self.config['width'] = float(settings.value('width', 10))
        self.config['height'] = float(settings.value('height', 20))
        self.config['angle'] = float(settings.value('angle', 0))

        settings.setValue('width', self.config['width'])
        settings.setValue('height', self.config['height'])
        settings.setValue('angle', self.config['angle'])
        settings.endGroup()
        settings.beginGroup('QRectangleCreator/Presets')
        if hasattr(self, 'preset_size_dropdown') and self.preset_size_dropdown is not None:
            for preset_name in settings.childKeys():
                self.preset_size_dropdown.addItem(preset_name)
        self.config["presets"] = {
            "Small": {
                "width": 10,
                "height": 20,
                "angle": 0
            },
            "Medium": {
                "width": 20,
                "height": 40,
                "angle": 0
            },
            "Large": {
                "width": 40,
                "height": 80,
                "angle": 0
            }

        }
        for preset_name in settings.childKeys():
            self.config["presets"][preset_name] = settings.value(preset_name)
        settings.endGroup()

    @try_catch
    def save_settings(self):
        settings = QgsSettings()
        settings.beginGroup('QRectangleCreator')
        settings.setValue('width', self.config['width'])
        settings.setValue('height', self.config['height'])
        settings.setValue('angle', self.config['angle'])
        settings.endGroup()
        settings.sync()
    @try_catch
    def settingsChanged(self, settings):
        self.config |= settings
        self.updateToolbar(settings)
        if hasattr(self, "drawingObject") and  isinstance(self.drawingObject, StartDrawing) and self.drawingObject is not None:
            self.drawingObject.setConfiguration(self.config['width'], self.config['height'], self.config['angle'])
            # self.drawingObject.canvasMoveEvent(None)
        if isinstance(self.settingsDlg, SettingsDialog) and self.settingsDlg is not None:
            self.settingsDlg.width.setValue(self.config['width'])
            self.settingsDlg.height.setValue(self.config['height'])
            self.settingsDlg.angle.setValue(self.config['angle'])
        self.save_settings()

    def add_action(
            self,
            icon_path,
            text,
            callback,
            enabled_flag=True,
            add_to_menu=True,
            add_to_toolbar=True,
            status_tip=None,
            whats_this=None,
            parent=None,
            checkable=False,
            checked=False,
            shortcut=None):

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolsToolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        if checkable:
            action.setCheckable(True)

        if checked:
            action.setChecked(1)

        if shortcut:
            action.setShortcut(shortcut)

        self.actions.append(action)

        return action

    @try_catch
    def initGui(self):
        icon_path = ':/plugins/QRectangleCreator/icons/'

        # LoginButton
        self.mainButton.setIcon(QIcon(icon_path + 'addRectangle.png'))
        self.mainButton.setPopupMode(QToolButton.MenuButtonPopup)
        self.mainButton.clicked.connect(self.run)
        self.mainButton.setToolTip('Add Rectangle')
        self.mainButton.setEnabled(True)
        self.mainButton.setCheckable(True)
        self.mainButton.setMenu(QMenu())
        self.toolsToolbar.addWidget(self.mainButton)

        # SettingsButton
        self.SettingsButton = self.add_action(
            icon_path + 'addRectangle.png',
            text=self.tr(u'Settings'),
            callback=self.settings,
            parent=self.iface.mainWindow(),
            add_to_menu=False,
            enabled_flag=False,
            add_to_toolbar=False)
        m = self.mainButton.menu()
        m.addAction(self.SettingsButton)

        # TextBox for width, height, and angle

        char_width = self.h_box.fontMetrics().averageCharWidth()
        self.w_box.setFixedWidth(10 * char_width)
        self.h_box.setFixedWidth(10 * char_width)
        self.a_box.setFixedWidth(10 * char_width)

        self.h_box.setText(str(self.config['height']))
        self.w_box.setText(str(self.config['width']))
        self.a_box.setText(str(self.config['angle']))

        self.h_box.editingFinished.connect(lambda :self.updateHeight(self.h_box.text()))
        self.w_box.editingFinished.connect(lambda :self.updateWidth(self.w_box.text()))
        self.a_box.editingFinished.connect(lambda :self.updateAngle(self.a_box.text()))
        self.toolsToolbar.addWidget(self.h_box)
        self.toolsToolbar.addWidget(self.w_box)
        self.toolsToolbar.addWidget(self.a_box)

        # Preset size dropdown
        self.preset_size_dropdown.addItems(self.config["presets"].keys())
        self.preset_size_dropdown.currentIndexChanged.connect(self.updatePresetSize)
        self.toolsToolbar.addWidget(self.preset_size_dropdown)
        # Add to Presets button
        self.add_to_presets_button.setText("Add to Presets")
        self.add_to_presets_button.clicked.connect(self.addToPresets)
        self.toolsToolbar.addWidget(self.add_to_presets_button)
        # Remove from Presets button
        self.remove_from_presets_button.setText("Remove from Presets")
        self.remove_from_presets_button.clicked.connect(self.removeFromPresets)
        self.toolsToolbar.addWidget(self.remove_from_presets_button)


        self.first_start = True
    @try_catch
    def removeFromPresets(self, e):
        current_preset = self.preset_size_dropdown.currentText()
        if current_preset in self.config["presets"]:
            del self.config["presets"][current_preset]
            settings = QgsSettings()
            settings.beginGroup('QRectangleCreator/Presets')
            settings.remove(current_preset)
            settings.endGroup()
            self.preset_size_dropdown.removeItem(self.preset_size_dropdown.currentIndex())

    @try_catch
    def addToPresets(self, e):
        preset_name, ok = QInputDialog.getText(self.iface.mainWindow(), "Add Preset", "Enter preset name:")
        if ok and preset_name:
            new_preset = {
                'width': self.config['width'],
                'height': self.config['height'],
                'angle': self.config['angle']
            }
            settings = QgsSettings()
            settings.beginGroup('QRectangleCreator/Presets')
            settings.setValue(preset_name, new_preset)
            settings.endGroup()
            self.preset_size_dropdown.addItem(preset_name)


    @try_catch
    def updatePresetSize(self, index):
        if "presets" not in self.config.keys():
            return
        if index < 0 or index >= len(self.config["presets"]):
            return
        presets = self.config["presets"]
        name = self.preset_size_dropdown.itemText(index)
        if name in presets:
            self.settingsChanged(presets[name])
    @try_catch
    def updateToolbar(self, settings):
        self.config.update(settings)
        self.h_box.setText(str(self.config['height']))
        self.w_box.setText(str(self.config['width']))
        self.a_box.setText(str(self.config['angle']))
        self.settingsDlg.width.setValue((self.config['width']))
        self.settingsDlg.height.setValue((self.config['height']))
        self.settingsDlg.angle.setValue((self.config['angle']))




    @try_catch
    def unload(self):
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&QRectangleCreator'),
                action)
            self.iface.removeToolBarIcon(action)

    def run(self):
        if self.first_start == True:
            self.first_start = False

        if self.mainButton.isChecked() == 1:
            self.drawingObject = StartDrawing(self.iface.mapCanvas(), self.iface, self)
            self.drawingObject.setConfiguration(
                self.settingsDlg.width.value(),
                self.settingsDlg.height.value(),
                self.settingsDlg.angle.value())
            self.iface.mapCanvas().setMapTool(self.drawingObject)
            self.SettingsButton.setEnabled(True)
        else:
            self.iface.mapCanvas().unsetMapTool(self.drawingObject)
            self.drawingObject.reset()
            self.SettingsButton.setEnabled(False)

    def settings(self):
        self.settingsDlg.width.setValue (self.config['width'])
        self.settingsDlg.height.setValue(self.config['height'])
        self.settingsDlg.angle.setValue (self.config['angle'])
        self.settingsDlg.show()
        current_width = self.settingsDlg.width.value()
        current_height = self.settingsDlg.height.value()
        current_angle = self.settingsDlg.angle.value()

        if self.settingsDlg.exec_() != 1:
            self.settingsDlg.width.setValue(current_width)
            self.settingsDlg.height.setValue(current_height)
            self.settingsDlg.angle.setValue(current_angle)

    # def settingsChanged(self):
    #     self.drawingObject.setConfiguration(
    #         self.settingsDlg.width.value(),
    #         self.settingsDlg.height.value(),
    #         self.settingsDlg.angle.value())


class StartDrawing(QgsMapToolEmitPoint):
    @try_catch
    def __init__(self, canvas, iface, parent):
        self.parent: QRectangleCreator = parent
        logger.error('StartDrawing')

        QgsMapToolEmitPoint.__init__(self, canvas)

        # qgis interface
        self.canvas = canvas
        self.iface = iface

        # snap marker
        self.snap_mark = QgsVertexMarker(self.canvas)
        self.snap_mark.setColor(QColor(0, 0, 255))
        self.snap_mark.setPenWidth(2)
        self.snap_mark.setIconType(QgsVertexMarker.ICON_BOX)
        self.snap_mark.setIconSize(10)

        # rectangle
        self.rubberBand = QgsRubberBand(self.canvas, QgsWkbTypes.GeometryType(3))
        self.rubberBand.setWidth(3)
        self.rubberBand.setStrokeColor(QColor(254, 0, 0))

        self.reset()

    @try_catch
    def setConfiguration(self, width, height, angle):
        self.parent.config['width'] = width
        self.parent.config['height'] = height
        self.parent.config['angle'] = angle

    def reset(self):
        self.rubberBand.reset(QgsWkbTypes.GeometryType(3))
        self.isEmittingPoint = False

    @try_catch
    def canvasMoveEvent(self, e):
        self.snap_mark.hide()
        self.snapPoint = False
        self.rubberBand.reset(QgsWkbTypes.GeometryType(3))

        self.snapPoint = self.checkSnapToPoint(e.pos())

        if self.snapPoint[0]:
            self.snap_mark.setCenter(self.snapPoint[1])
            self.snap_mark.show()
            self.rectangle = self.getRectangle(self.snapPoint[1])
        else:
            self.rectangle = self.getRectangle(self.toMapCoordinates(e.pos()))
        self.rubberBand.setToGeometry(self.rectangle, None)
        self.rubberBand.show()

    @try_catch
    def wheelEvent(self, e):
        logger.error('wheelEvent')
        if e.modifiers() == Qt.ShiftModifier:
            logger.error('wheelEvent Shift')
            if e.angleDelta().y() > 0:
                logger.error(f"wheelEvent {self.parent.config['angle']} -> {self.parent.config['angle'] - 5}")
                self.parent.updateAngle(self.parent.config['angle']-5)
            else:
                # logger.error('wheelEvent Shift')
                logger.error(f"wheelEvent {self.parent.config['angle']} -> {self.parent.config['angle'] + 5}")
                self.parent.updateAngle(self.parent.config['angle']+5)
            self.rubberBand.reset(QgsWkbTypes.GeometryType(3))
            self.rubberBand.setToGeometry(self.rectangle, None)
            self.rubberBand.show()
            e.accept()
            # self.parent.updateAngle(self.parent.config['angle'])
        self.canvasMoveEvent(e)

    @try_catch
    def checkSnapToPoint(self, point):
        snapped = False
        snap_point = self.toMapCoordinates(point)
        snapper = self.canvas.snappingUtils()
        snapMatch = snapper.snapToMap(point)
        if snapMatch.hasVertex():
            snap_point = snapMatch.point()
            snapped = True
        return snapped, snap_point

    @try_catch
    def canvasPressEvent(self, e):
        if self.snapPoint == False:
            point = self.toMapCoordinates(self.canvas.mouseLastXY())
        else:
            point = self.snapPoint[1]

        layer = self.iface.activeLayer()

        layer_crs = layer.crs().authid()
        layer_crs = QgsCoordinateReferenceSystem(layer_crs)
        canvas_crs = self.canvas.mapSettings().destinationCrs().authid()
        canvas_crs = QgsCoordinateReferenceSystem(canvas_crs)
        crs2crs = QgsCoordinateTransform(canvas_crs, layer_crs, QgsProject.instance())

        feature = QgsFeature()
        fields = layer.fields()
        feature.setFields(fields)

        if layer.wkbType() == QgsWkbTypes.Polygon or layer.wkbType() == QgsWkbTypes.MultiPolygon:
            if layer_crs == canvas_crs:
                feature.setGeometry(self.rectangle)
            else:
                geom = self.rectangle
                geom.transform(crs2crs)
                feature.setGeometry(geom)

            if "rotation" in fields.names():
                logger.error(f"rotation: {self.parent.config['angle']}")
                feature.setAttribute("rotation", self.parent.config['angle'])
            if "width" in fields.names():
                logger.error(f"width: {self.parent.config['width']}")
                feature.setAttribute("width", self.parent.config['width'])
            if "height" in fields.names():
                logger.error(f"height: {self.parent.config['height']}")
                feature.setAttribute("height", self.parent.config['height'])

            layer.startEditing()
            layer.addFeature(feature)
            layer.commitChanges()
            layer.reload()
        else:
            self.iface.messageBar().pushCritical('QRectangle Creator: ',
                                                 'The current layer is not of Polygon or MultiPolygon type. The object has not been added')
        raise Exception("End of drawing")
    @try_catch
    def getRectangle(self, point):
        polygon = QgsWkbTypes.GeometryType(3)

        x = point.x()
        y = point.y()

        points = [[
            QgsPointXY(  # Left Top corner
                x - (self.parent.config['width'] / 2),
                y + (self.parent.config['height'] / 2)
            ),
            QgsPointXY(  # Right Top corner
                x + (self.parent.config['width'] / 2),
                y + (self.parent.config['height'] / 2)
            ),
            QgsPointXY(  # Right Down corner
                x + (self.parent.config['width'] / 2),
                y - (self.parent.config['height'] / 2)
            ),
            QgsPointXY(  # Left Down corner
                x - (self.parent.config['width'] / 2),
                y - (self.parent.config['height'] / 2)
            )
        ]]
        polygon = QgsGeometry.fromPolygonXY(points)
        polygon.rotate(self.parent.config['angle'], point)
        return polygon


FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), 'settings.ui'))


class SettingsDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        super(SettingsDialog, self).__init__(parent)
        self.setupUi(self)
