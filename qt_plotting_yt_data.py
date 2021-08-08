from PyQt5.QtWidgets import *
import ui_design, json, pytz, random
from PyQt5.QtSql import *
from PyQt5.QtCore import *
from datetime import *
import numpy as np
import pandas as pd
import matplotlib.dates as mdates
import matplotlib.ticker as plticker
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.colors
import seaborn as sns
# using code from https://stackoverflow.com/questions/43947318/plotting-matplotlib-figure-inside-qwidget-using-qt-designer-form-and-pyqt5

class MyApp(QMainWindow, ui_design.Ui_MainWindow):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.setupUi(self)
        self.startQueryButton.clicked.connect(self.plot_data)
        self.startDateTimeEditor.setDisplayFormat("dd.MM.yyyy hh:mm")
        self.endDateTimeEditor.setDisplayFormat("dd.MM.yyyy hh:mm")
        self.pgsql_config_file = open("postgres-config-qt.json")
        self.pgsql_creds = json.load(self.pgsql_config_file)
        self.populate_widgets()

    def plot_data(self):
        self.plotWidget.canvas.ax.clear()
        startTime = self.startDateTimeEditor.dateTime()
        endTime = self.endDateTimeEditor.dateTime()
        startTime.setOffsetFromUtc(0)
        endTime.setOffsetFromUtc(0)
        self.plotWidget.canvas.ax.set_xlim(startTime.toPyDateTime().date(),endTime.toPyDateTime().date())
        datetime_list, date_list, time_list, donation_list = self.get_time_series_data(startTime,endTime)
        self.plotWidget.canvas.ax.scatter(date_list, time_list)
        yFmt = mdates.DateFormatter('%H:%M')
        xFmt = mdates.DateFormatter('%d.%m.%y')
        self.plotWidget.canvas.ax.xaxis.set_major_formatter(xFmt)
        self.plotWidget.canvas.ax.yaxis.set_major_formatter(yFmt)
        self.plotWidget.canvas.ax.set_title("Superchat time")
        self.plotWidget.canvas.ax.set_ylabel("Time of day")
        self.plotWidget.canvas.ax.set_xlabel("Date")
        self.plotWidget.canvas.draw()
        self.plotWidget_2.canvas.ax.clear()
        self.plotWidget_2.canvas.ax.set_xlim(startTime.toPyDateTime().date(),endTime.toPyDateTime().date())
        self.plotWidget_2.canvas.ax.set_ylim(0.0,24.0)
        self.plotWidget_2.canvas.ax.xaxis.set_major_formatter(xFmt)
        self.plotWidget_2.canvas.ax.set_title("Streaming times")
        self.plotWidget_2.canvas.ax.set_ylabel("Time of day")
        self.plotWidget_2.canvas.ax.set_xlabel("Date")
        loc = plticker.MultipleLocator(base=2.0) # this locator puts ticks at regular intervals
        checked_chans = []
        for index in range(self.channelListWidget.count()):
            if self.channelListWidget.item(index).checkState() == Qt.Checked:
                checked_chans.append(self.channelListWidget.item(index))
        namelist = [x.text() for x in checked_chans]
        patches=[]
        self.color_dict = self.getcolors(namelist)
        for name in namelist:
            stream_list = []
            stream_list = stream_list + self.get_past_schedule(startTime,endTime,name)
            stream_list_new = []
            col = self.choose_color(name)
            #print(col)
            patches.append(mpatches.Patch(color=col, label = name))
            for stream in stream_list:
                stream_list_new = stream_list_new + self.check_midnight(stream[0],stream[1])
            for stream in stream_list_new:
                x_range = [(stream[0].date(),timedelta(days=1))]
                y_range = (self.time2delta(stream[0].timetz()).seconds/60.0/60.0,stream[1].seconds/60.0/60.0)
                self.plotWidget_2.canvas.ax.broken_barh(x_range,y_range, alpha = 0.5, color = col)
        self.plotWidget_2.canvas.ax.yaxis.set_major_locator(loc)
        self.plotWidget_2.canvas.ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.15), ncol=3, handles=patches)
        self.plotWidget_2.canvas.draw()
        
    def populate_widgets(self):
        self.db = QSqlDatabase.addDatabase('QPSQL')
        self.db.setHostName(self.pgsql_creds["host"])
        self.db.setUserName(self.pgsql_creds["username"])
        self.db.setPassword(self.pgsql_creds["password"])
        self.db.setDatabaseName(self.pgsql_creds["database"])
        self.db.open()
        query = QSqlQuery()
        query.exec_("select name from channel inner join video v on id = v.channel_id group by name order by name")
        while query.next():
            #print(query.value(0))
            entry = QListWidgetItem(query.value(0).strip())
            entry.setCheckState(Qt.Unchecked)
            self.channelListWidget.addItem(entry)
        query.exec_("select currency from messages group by currency order by currency")
        while query.next():
            #print(query.value(0))
            entry = QListWidgetItem(query.value(0).strip())
            entry.setCheckState(Qt.Checked)
            self.currencyListWidget.addItem(entry)
        self.db.close()
    
    def check_midnight(self,startdatetime,duration):
        oldtime = startdatetime
        newtime = startdatetime + duration
        if oldtime.date() != newtime.date():
            newmidnight = newtime.replace(hour=0, minute=0, second=0, microsecond=0)
            timetomidnight = newmidnight - oldtime
            timetofinish = newtime - newmidnight
            #print([(oldtime,timetomidnight),(newmidnight,timetofinish)])
            return [(oldtime,timetomidnight),(newmidnight,timetofinish)]
        else:
            return [(oldtime,duration)]
            
    def time2delta(self,thetime):
        return timedelta(seconds=thetime.second+thetime.minute*60+thetime.hour*60*60, microseconds = thetime.microsecond)
    
    def choose_color(self,name):
        if name in self.color_dict.keys():
            col = self.color_dict[name]
        else:
            r = random.random()
            b = random.random()
            g = random.random()
            col = (r, g, b)
        #print(col)
        return col
    
    def getcolors(self,namelist):
        self.db.open()
        color_dict = {}
        names = "("
        for n in namelist:
            names = names + "'"+n.replace("'","''")+"',"
        if len(names) <= 1:
            names = names + "'None')"
        else:
            names = names[:-1] + ")"
        query = QSqlQuery()
        query.prepare("select color, id, name from channel where name in "+names+" and color is not null")
        query.exec_()
        while query.next():
            h = "#"+query.value(0)
            db_color = matplotlib.colors.to_rgb(h)
            color_dict[query.value(2)] = db_color
        self.db.close()
        return color_dict
    
    def get_past_schedule(self,startTime,endTime,chan_name="None"):
        #names = "("
        #for n in namelist:
        #    names = names + "'"+n.replace("'","''")+"',"
        #if len(names) <= 1:
        #    names = names + "'None')"
        #else:
        #    names = names[:-1] + ")"
        self.db.open()
        query = QSqlQuery()
        query.prepare("select actualstarttime AT TIME ZONE 'UTC', length from video inner join channel c on c.id = channel_id where c.name = :name and length <> 0 and actualstarttime >= :start and actualstarttime < :end")
        query.bindValue(":name",chan_name)
        query.bindValue(":start",startTime)
        query.bindValue(":end",endTime)
        query.exec_()
        #print(query.lastQuery())
        stream_list = []
        while query.next():
            stream_list.append((query.value(0).toPyDateTime(),timedelta(seconds=query.value(1))))
        self.db.close()
        return stream_list
        
    def get_time_series_data(self,startTime,endTime):
        #print(startTime.toString(), endTime.toString())
        checked_chans = []
        for index in range(self.channelListWidget.count()):
            if self.channelListWidget.item(index).checkState() == Qt.Checked:
                checked_chans.append(self.channelListWidget.item(index))
        namelist = [x.text() for x in checked_chans]
        names = "("
        for n in namelist:
            names = names + "'"+n.replace("'","''")+"',"
        if len(names) <= 1:
            names = names + "'None')"
        else:
            names = names[:-1] + ")"
        checked_currencies = []
        for index in range(self.currencyListWidget.count()):
            if self.currencyListWidget.item(index).checkState() == Qt.Checked:
                checked_currencies.append(self.currencyListWidget.item(index))
        currencylist = [x.text() for x in checked_currencies]
        currencies = json.dumps(currencylist).replace("[","(").replace("]",")").replace('"',"'")
        #print(namelist,currencylist)
        self.db.open()
        query = QSqlQuery()
        query.prepare("SELECT time_sent AT TIME ZONE 'UTC', extract(hour from time_sent AT TIME ZONE 'UTC') as hour, extract(minute from time_sent AT TIME ZONE 'UTC') as minute, currency, value from messages inner join video v on v.video_id = messages.video_id inner join channel c on c.id = v.channel_id WHERE c.name IN "+names+" and currency in "+currencies+" and time_sent >= :start and time_sent < :end ORDER BY hour")
        query.bindValue(":start",startTime)
        query.bindValue(":end",endTime)
        query.exec_()
        #print(query.lastQuery())
        datetime_list = []
        date_list = []
        time_list = []
        donation_list = []
        while query.next():
            #print(type(query.value(0)),type(query.value(1)),type(query.value(2)),type(query.value(3)),type(query.value(4)))
            #print(query.value(0),query.value(1),query.value(2),query.value(3),query.value(4))
            date_list.append(query.value(0).toPyDateTime().replace(hour=0, minute=0, second=0, microsecond=0))
            time_list.append(datetime(1970,1,1,int(query.value(1)),int(query.value(2)),tzinfo = timezone.utc))
            datetime_list.append(query.value(0).toPyDateTime())
            donation_list.append((query.value(4),query.value(3).strip()))
        self.db.close()
        return datetime_list, date_list, time_list, donation_list
            