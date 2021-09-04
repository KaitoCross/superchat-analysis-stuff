# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'visual.ui'
#
# Created by: PyQt5 UI code generator 5.15.4
#
# WARNING: Any manual changes made to this file will be lost when pyuic5 is
# run again.  Do not edit this file unless you know what you are doing.


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(1280, 720)
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.channelListWidget = QtWidgets.QListWidget(self.centralwidget)
        self.channelListWidget.setGeometry(QtCore.QRect(1020, 10, 256, 301))
        self.channelListWidget.setObjectName("channelListWidget")
        self.currencyListWidget = QtWidgets.QListWidget(self.centralwidget)
        self.currencyListWidget.setGeometry(QtCore.QRect(1020, 320, 256, 261))
        self.currencyListWidget.setObjectName("currencyListWidget")
        self.startQueryButton = QtWidgets.QPushButton(self.centralwidget)
        self.startQueryButton.setGeometry(QtCore.QRect(1020, 650, 251, 23))
        self.startQueryButton.setObjectName("startQueryButton")
        self.startDateTimeEditor = QtWidgets.QDateTimeEdit(self.centralwidget)
        self.startDateTimeEditor.setGeometry(QtCore.QRect(1020, 590, 194, 24))
        self.startDateTimeEditor.setObjectName("startDateTimeEditor")
        self.endDateTimeEditor = QtWidgets.QDateTimeEdit(self.centralwidget)
        self.endDateTimeEditor.setGeometry(QtCore.QRect(1020, 620, 194, 24))
        self.endDateTimeEditor.setObjectName("endDateTimeEditor")
        self.tabWidget = QtWidgets.QTabWidget(self.centralwidget)
        self.tabWidget.setGeometry(QtCore.QRect(0, 0, 1021, 681))
        self.tabWidget.setObjectName("tabWidget")
        self.sc_tab = QtWidgets.QWidget()
        self.sc_tab.setObjectName("sc_tab")
        self.plotWidget = MplWidget(self.sc_tab)
        self.plotWidget.setGeometry(QtCore.QRect(10, 10, 1001, 641))
        self.plotWidget.setObjectName("plotWidget")
        self.tabWidget.addTab(self.sc_tab, "")
        self.timetable_tab = QtWidgets.QWidget()
        self.timetable_tab.setObjectName("timetable_tab")
        self.plotWidget_2 = MplWidget(self.timetable_tab)
        self.plotWidget_2.setGeometry(QtCore.QRect(10, 10, 1001, 641))
        self.plotWidget_2.setObjectName("plotWidget_2")
        self.tabWidget.addTab(self.timetable_tab, "")
        self.superchatreading_tab = QtWidgets.QWidget()
        self.superchatreading_tab.setObjectName("superchatreading_tab")
        self.superchat_view = QtWidgets.QTableView(self.superchatreading_tab)
        self.superchat_view.setGeometry(QtCore.QRect(10, 30, 1001, 581))
        self.superchat_view.setObjectName("superchat_view")
        self.superchat_menu = QtWidgets.QComboBox(self.superchatreading_tab)
        self.superchat_menu.setGeometry(QtCore.QRect(10, 0, 1001, 23))
        self.superchat_menu.setObjectName("superchat_menu")
        self.getSCbutton = QtWidgets.QPushButton(self.superchatreading_tab)
        self.getSCbutton.setGeometry(QtCore.QRect(910, 620, 101, 23))
        self.getSCbutton.setObjectName("getSCbutton")
        self.getStreamListButton = QtWidgets.QPushButton(self.superchatreading_tab)
        self.getStreamListButton.setGeometry(QtCore.QRect(790, 620, 101, 23))
        self.getStreamListButton.setObjectName("getStreamListButton")
        self.tabWidget.addTab(self.superchatreading_tab, "")
        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 1280, 20))
        self.menubar.setObjectName("menubar")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)
        self.tabWidget.setCurrentIndex(2)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "visualize Superchat times"))
        self.startQueryButton.setText(_translate("MainWindow", "query database/draw"))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.sc_tab), _translate("MainWindow", "Superchat timing"))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.timetable_tab), _translate("MainWindow", "streaming schedule"))
        self.getSCbutton.setText(_translate("MainWindow", "Get superchats"))
        self.getStreamListButton.setText(_translate("MainWindow", "get stream list"))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.superchatreading_tab), _translate("MainWindow", "superchat reading"))
from mplwidget import MplWidget
