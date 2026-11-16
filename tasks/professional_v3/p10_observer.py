"""Read-only QGIS GUI instrumentation; records no reference values or grades."""
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from qgis.core import QgsProject, QgsCoordinateTransform, QgsPointXY, NULL
from qgis.PyQt.QtCore import QTimer, QPoint
from qgis.PyQt.QtWidgets import QApplication
from qgis.utils import iface


snapshot = {}


def refresh():
    global snapshot
    try:
        canvas = iface.mapCanvas()
        layer = iface.activeLayer()
        tables = [widget for widget in QApplication.topLevelWidgets()
                  if widget.isVisible() and "AttributeTable" in widget.metaObject().className()]
        selected = []
        visible = False
        if layer and hasattr(layer, "selectedFeatures"):
            transform = QgsCoordinateTransform(layer.crs(), canvas.mapSettings().destinationCrs(), QgsProject.instance())
            for feature in layer.selectedFeatures()[:20]:
                selected.append({field.name(): None if feature[field.name()] == NULL else feature[field.name()] for field in layer.fields()})
                center = transform.transform(QgsPointXY(feature.geometry().boundingBox().center()))
                pixel = canvas.mapSettings().mapToPixel().transform(center)
                point = QPoint(round(pixel.x()), round(pixel.y()))
                global_point = canvas.mapToGlobal(point)
                visible |= canvas.rect().contains(point) and not any(table.frameGeometry().contains(global_point) for table in tables)
        layouts = []
        for designer in iface.openLayoutDesigners():
            if designer.window().isVisible():
                layouts.append(designer.masterLayout().name())
        snapshot = {"timestamp": time.time(), "pid": os.getpid(), "project": QgsProject.instance().fileName(),
            "dirty": QgsProject.instance().isDirty(), "active_layer": layer.name() if layer else None,
            "canvas_visible": canvas.isVisible(), "table_visible": bool(tables), "selected": selected,
            "selection_in_canvas": bool(visible), "layouts_visible": layouts,
            "layers": [{"id": current.id(), "name": current.name(), "source": current.source()} for current in QgsProject.instance().mapLayers().values()]}
    except Exception as error:
        snapshot = {"timestamp": time.time(), "pid": os.getpid(), "error": type(error).__name__ + ": " + str(error)}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        payload = json.dumps(snapshot).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_args):
        pass


server = HTTPServer(("127.0.0.1", 18763), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
timer = QTimer(iface.mainWindow())
timer.timeout.connect(refresh)
timer.start(200)
refresh()
