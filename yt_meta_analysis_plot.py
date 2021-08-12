from PyQt5 import QtWidgets
import sys

# Local Module Imports
import qt_plotting_yt_data as af

# Create GUI application
app = QtWidgets.QApplication(sys.argv)
form = af.MyApp()
form.show()
app.exec_()