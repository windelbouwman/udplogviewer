#!/usr/bin/env python

# -*- coding: utf-8 -*-

"""
Logviewer that can handle log messages over the logging system and udp.

Greatly copied from logviewer existing project.
"""

import logging
import struct
import pickle
import time

# TODO: make other Qt bindings possible (pyside):
try:
    from PyQt5.QtCore import QSortFilterProxyModel, QObject, Qt, pyqtSignal
    from PyQt5.QtCore import QAbstractTableModel, QModelIndex
    from PyQt5.QtWidgets import QWidget, QLineEdit, QTableView, QVBoxLayout
    from PyQt5.QtWidgets import QApplication, QLabel
    from PyQt5.QtNetwork import QUdpSocket, QHostAddress
except ImportError:
    from PyQt4.QtCore import Qt, QObject, QModelIndex, QAbstractTableModel
    from PyQt4.QtGui import QSortFilterProxyModel
    from PyQt4.QtGui import QApplication, QWidget, QLineEdit
    from PyQt4.QtGui import QVBoxLayout, QTableView, QLabel
    from PyQt4.QtNetwork import QUdpSocket, QHostAddress


def convert_datagram(chunk):
    """ Unpack a udp datagram into a log record """
    slen = struct.unpack('>L', chunk[:4])[0]
    chunk = chunk[4:]
    assert slen == len(chunk)
    obj = pickle.loads(chunk)
    record = logging.makeLogRecord(obj)
    return record


class UdpHandler(QObject):
    """ Listens to a udp port. Default is port 9021 """
    def __init__(self, model, port=9021):
        super().__init__()
        self._model = model
        self._socket = QUdpSocket(self)
        self._socket.bind(QHostAddress.Any, port)
        self._socket.readyRead.connect(self.readDatagrams)

    def readDatagrams(self):
        datagrams = []
        while self._socket.hasPendingDatagrams():
            datagram_size = self._socket.pendingDatagramSize()
            datagram, _, _ = self._socket.readDatagram(datagram_size)
            datagrams.append(datagram)

        records = [convert_datagram(datagram) for datagram in datagrams]
        self._model.add_records(records)


class UdpLogReceiver(QWidget):
    """
        Log events generated by python logging objects.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._model = LogRecordModel()
        filter_model = QSortFilterProxyModel()
        filter_model.setSourceModel(self._model)
        filter_model.setFilterKeyColumn(3)

        self.msg_filter = QLineEdit()
        self.log_view = QTableView()
        self.log_view.setModel(filter_model)
        header = self.log_view.horizontalHeader()
        #header.setSectionResizeMode(header.Stretch)
        header.setStretchLastSection(True)
        self.status_label = QLabel()

        # Connect signals:
        self.msg_filter.textChanged.connect(filter_model.setFilterFixedString)
        # Make nice layout:
        layout = QVBoxLayout(self)
        layout.addWidget(self.msg_filter)
        layout.addWidget(self.log_view)
        layout.addWidget(self.status_label)

        # Attach udp server:
        self._udpServer = UdpHandler(self._model)
        self._model.stats_changed.connect(self.status_label.setText)


class LogRecordModel(QAbstractTableModel):
    """ Model that contains all log messages """
    stats_changed = pyqtSignal(str)
    def __init__(self):
        super().__init__()
        self.records = []
        self.cols = ('created', 'levelname', 'name', 'msg')
        def conv_time(t):
            return time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(t))
        self.conv_map = {}
        self.conv_map['created'] = conv_time

    def add_records(self, records):
        """ Add multiple records at once """
        if not records:
            return
        pos = len(self.records)
        self.beginInsertRows(QModelIndex(), pos, pos + len(records) - 1)
        self.records.extend(records)
        self.endInsertRows()
        self.stats_changed.emit('{} records'.format(len(self.records)))

    def rowCount(self, parent):
        return len(self.records)

    def columnCount(self, parent):
        return len(self.cols)

    def data(self, index, role):
        if index.isValid():
            record = self.records[index.row()]
            attr = self.cols[index.column()]
            if role == Qt.DisplayRole:
                v = getattr(record, attr)
                if attr in self.conv_map:
                    v = self.conv_map[attr](v)
                v = str(v)
                return v

    def headerData(self, section, orientation, role):
        if orientation == Qt.Horizontal and \
                role == Qt.DisplayRole:
            return self.cols[section]


if __name__ == '__main__':
    app = QApplication([])
    view = UdpLogReceiver()
    view.show()
    app.exec_()
