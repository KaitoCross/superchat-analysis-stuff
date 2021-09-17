from PyQt5.QtWidgets import *
import ui_design, json, pytz, random
from PyQt5.QtSql import *
from PyQt5.QtCore import *
from PyQt5.QtGui import QColor, QBrush
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
        self.setFixedWidth(1600)
        self.setFixedHeight(900)
        self.startQueryButton.clicked.connect(self.plot_data)
        self.getStreamListButton.clicked.connect(self.get_stream_list)
        self.getSCbutton.clicked.connect(self.get_superchats)
        self.startDateTimeEditor.setDisplayFormat("dd.MM.yyyy hh:mm")
        self.endDateTimeEditor.setDisplayFormat("dd.MM.yyyy hh:mm")
        self.curr = {"Africa": ["ZAR","EGP"],
                "Asia": ["AED","HKD","INR","JOD","JPY","KRW","MYR","PHP","QAR","SAR","SGD","TWD"],
                "Europe": ["BAM","BGN","BYN","CHF","CZK","DKK","EUR","GBP","HRK","HUF","ILS","ISK","NOK","PLN","RON","RSD","RUB","SEK","TRY"],
                "North America": ["USD","CAD","MXN"],
                "South America": ["ARS","BOB","BRL","CLP","COP","CRC","DOP","GTQ","HNL","NIO","PEN","PYG","UYU"],
                "Oceania": ["AUD","NZD"]}
        self.pgsql_config_file = open("postgres-config-qt.json")
        self.pgsql_creds = json.load(self.pgsql_config_file)
        self.sc_model = MySqlModel()
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
        self.plotWidget_2.canvas.ax.set_xlim(startTime.toPyDateTime(),endTime.toPyDateTime())
        self.plotWidget_2.canvas.ax.set_ylim(0.0,24.0)
        self.plotWidget_2.canvas.ax.xaxis.set_major_formatter(xFmt)
        self.plotWidget_2.canvas.ax.set_title("Streaming times")
        self.plotWidget_2.canvas.ax.set_ylabel("Time of day")
        self.plotWidget_2.canvas.ax.set_xlabel("Date")
        heatmap_data = np.zeros((7,24))
        loc = plticker.MultipleLocator(base=2.0) # this locator puts ticks at regular intervals
        checked_chans = []
        for index in range(self.channelListWidget.count()):
            if self.channelListWidget.item(index).checkState() == Qt.Checked:
                checked_chans.append(self.channelListWidget.item(index))
        namelist = [x.text() for x in checked_chans]
        namelist.sort()
        patches=[]
        self.color_dict = self.getcolors(namelist)
        self.color_dict["Europe"] = (0.0,0.0,1.0)
        self.color_dict["North America"] = (1.0,0.0,0.0)
        self.color_dict["Asia"] = (0.0,1.0,0.0)
        self.color_dict["Oceania"] = (0.0,0.0,0.0)
        self.color_dict["Africa"] = (1.0,1.0,0.0)
        self.color_dict["South America"] = (1.0,165/255.0,0.0)
        namecount = 0
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
                time_width = timedelta(days=1) / len(namelist)
                stream_date = stream[0].replace(hour=0, minute=0, second=0, microsecond=0)
                x_range = [(stream_date+time_width*namecount,time_width)]
                y_range = (self.time2delta(stream[0].timetz()).seconds/60.0/60.0,stream[1].seconds/60.0/60.0)
                self.plotWidget_2.canvas.ax.broken_barh(x_range,y_range, alpha = 0.5, color = col)
                stream_hour = stream[0].replace(minute=0, second=0, microsecond=0)
                testtime = stream_hour
                endtime = stream[0] + stream[1]
                while testtime <= endtime:
                    heatmap_data[testtime.weekday()][testtime.time().hour] += 1
                    #if testtime.weekday() >= 0 and testtime.weekday() <= 4:
                    #    heatmap_data[7][testtime.time().hour] += 1
                    #elif testtime.weekday() >= 5:
                    #    heatmap_data[8][testtime.time().hour] += 1
                    testtime = testtime + timedelta(hours=1)
            namecount += 1
        print(heatmap_data)
        days = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']#,'Weekdays','Weekend']
        self.plotWidget_2.canvas.ax.yaxis.set_major_locator(loc)
        self.plotWidget_2.canvas.ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.15), ncol=3, handles=patches)
        self.plotWidget_2.canvas.draw()
        self.heatmap_widget.canvas.ax.clear()
        self.heatmap_widget.canvas.ax2.clear()
        #self.heatmap_widget.canvas.fig.clear()
        self.heatmap_widget.canvas.ax.set_title("Stream times heatmap")
        self.heatmap_widget.canvas.ax.set_ylabel("Day of week")
        self.heatmap_widget.canvas.ax.set_xlabel("Time of day")
        self.heatmap_widget.canvas.ax.set_xticks(np.arange(24))
        self.heatmap_widget.canvas.ax.set_yticks(np.arange(len(days)))
        self.heatmap_widget.canvas.ax.set_yticklabels(days)
        heatmap = plt.pcolor(heatmap_data)
        self.heatmap_widget.canvas.fig.colorbar(heatmap,self.heatmap_widget.canvas.ax2)
        self.heatmap_widget.canvas.ax.imshow(heatmap_data)
        for y in range(heatmap_data.shape[0]):
            for x in range(heatmap_data.shape[1]):
                text = self.plotWidget_2.canvas.ax.text(x, y, heatmap_data[y, x],ha="center", va="center", color="w")
        self.heatmap_widget.canvas.draw()
        #xFmt = mdates.DateFormatter('%H:%M')
        self.donortiming.canvas.ax.clear()
        self.donortiming.canvas.ax.set_title("Donors per currency at which time")
        self.donortiming.canvas.ax.xaxis.set_major_locator(loc)
        #self.donortiming.canvas.ax.xaxis.set_major_formatter(xFmt)
        self.donortiming.canvas.ax.set_ylabel("amount of unique superchatters")
        self.donortiming.canvas.ax.set_xlabel("Time of day")
        time_dict, coord_dict, area_sums = self.get_supa_time(startTime,endTime)
        for currency in coord_dict:
            self.donortiming.canvas.ax.plot(coord_dict[currency]["users"],label = currency, color = self.choose_color(currency))
        self.donortiming.canvas.ax.legend(loc="right")
        self.donortiming.canvas.draw()
        self.area_sc_timing_draw.canvas.ax.clear()
        self.area_sc_timing_draw.canvas.ax.xaxis.set_major_locator(loc)
        self.area_sc_timing_draw.canvas.ax.set_title("Donors per region at which time")
        self.area_sc_timing_draw.canvas.ax.set_ylabel("amount of unique superchatters")
        self.area_sc_timing_draw.canvas.ax.set_xlabel("Time of day")
        print(area_sums)
        for area in area_sums.keys():
            self.area_sc_timing_draw.canvas.ax.plot(area_sums[area], label = str(area), color = self.choose_color(area))
        self.area_sc_timing_draw.canvas.ax.legend(loc="right")
        self.area_sc_timing_draw.canvas.draw()
        
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
            
        for area in self.curr.keys():
            entry = QListWidgetItem(area)
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
        names = self.namelist_string(namelist)
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
        query.prepare("select actualstarttime AT TIME ZONE 'UTC', length, scheduledStartTime AT TIME ZONE 'UTC', endedLogAt AT TIME ZONE 'UTC', actualendtime AT TIME ZONE 'UTC', video_id from video inner join channel c on c.id = channel_id where c.name = :name and ((actualstarttime >= :start and actualstarttime < :end) or (scheduledStartTime >= :start and scheduledStartTime < :end))")
        query.bindValue(":name",chan_name)
        query.bindValue(":start",startTime)
        query.bindValue(":end",endTime)
        query.exec_()
        #print(query.lastQuery())
        stream_list = []
        unknowndur = timedelta(hours = 2)
        while query.next():
            starttime = query.value(0)
            starttime = starttime.toPyDateTime() if starttime else 0
            duration = timedelta(seconds=query.value(1))
            plannedstarttime = query.value(2).toPyDateTime()
            vid = query.value(5)
            endedLogAt = query.value(3)
            endedLogAt = endedLogAt.toPyDateTime() if endedLogAt else 0
            actualEndTime = query.value(4)
            actualEndTime = actualEndTime.toPyDateTime() if actualEndTime else 0
            if not starttime:
                starttime = plannedstarttime
            #print(starttime,duration,endedLogAt)
            if not duration:
                end_time = None
                if not endedLogAt:
                    now = datetime.utcnow()
                    tempend = starttime + unknowndur
                    endedLogAt = now if (now - starttime) < timedelta(hours = 12) else tempend
                    end_time = endedLogAt
                else:
                    end_time = endedLogAt
                if actualEndTime:
                    end_time = actualEndTime
                duration = end_time - starttime
                print("#",starttime,duration,end_time,vid)
                if end_time < starttime:
                    starttime = end_time - unknowndur
                    duration = unknowndur
            if starttime and duration:
                stream_list.append((starttime,duration))
        self.db.close()
        return stream_list
        
    def get_time_series_data(self,startTime,endTime):
        #print(startTime.toString(), endTime.toString())
        namelist = self.get_checked_chans()
        names = self.namelist_string(namelist)
        currencylist = self.get_checked_currencies()
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
    
    def get_stream_list(self):
        self.superchat_menu.clear()
        startTime = self.startDateTimeEditor.dateTime()
        endTime = self.endDateTimeEditor.dateTime()
        startTime.setOffsetFromUtc(0)
        endTime.setOffsetFromUtc(0)
        namelist = self.get_checked_chans()
        names = self.namelist_string(namelist)
        self.db.open()
        query = QSqlQuery()
        test = query.prepare("SELECT video_id, title, scheduledStartTime AT TIME ZONE 'UTC' from video inner join channel c on c.id = video.channel_id WHERE c.name IN "+names+" and scheduledStartTime >= :start and scheduledStartTime < :end ORDER BY scheduledStartTime")
        query.bindValue(":start",startTime)
        query.bindValue(":end",endTime)
        query.exec_()
        #print(test, query.lastQuery())
        while query.next():
            self.superchat_menu.addItem("["+query.value(2).toPyDateTime().isoformat() + "] " + query.value(1),query.value(0))
        self.db.close()
        
    def namelist_string(self,namelist):
        names = "("
        for n in namelist:
            names = names + "'"+n.replace("'","''")+"',"
        if len(names) <= 1:
            names = names + "'None')"
        else:
            names = names[:-1] + ")"
        return names
    
    def get_superchats(self):
        video_id = self.superchat_menu.currentData()
        currencylist = self.get_checked_currencies()
        currencies = json.dumps(currencylist).replace("[","(").replace("]",")").replace('"',"'")
        self.db.open()
        customquery = "select (select name from chan_names where id = user_id and time_discovered <= time_sent order by time_discovered desc limit 1) as username, '#' || lpad(to_hex(messages.color-4278190080),6,'0') as sc_color, value, currency, message_txt, time_sent from messages inner join channel c on user_id = c.id where video_id = '"+video_id+"' and currency in " + currencies + " order by time_sent"
        #query = QSqlQuery()
        #test = query.prepare("select video_id, c.name, message_txt, '#' || lpad(to_hex(messages.color-4278190080),6,'0') as sc_color, value, currency, time_sent from messages inner join channel c on user_id = c.id where video_id = :vid order by time_sent")
        #query.bindValue(":vid",video_id)
        #print(video_id,test)
        #quoted code not working - but that would be the proper way afaik (except currencies are not there yet)
        #print(customquery)
        self.sc_model.setQuery(customquery,self.db)
        self.superchat_view.setModel(self.sc_model)
        self.superchat_view.show()
        self.superchat_view.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        self.autoresize()

    def autoresize(self):
        tablehead = self.superchat_view.horizontalHeader()
        tablehead.setSectionResizeMode(1,QHeaderView.ResizeToContents)
        tablehead.setSectionResizeMode(2,QHeaderView.ResizeToContents)
        tablehead.setSectionResizeMode(3,QHeaderView.ResizeToContents)
        tablehead.setSectionResizeMode(4,QHeaderView.Stretch)
        tablehead.setSectionResizeMode(0,QHeaderView.Fixed)
        tablehead.resizeSection(0,200)
        #tablehead.resizeSections(QHeaderView.Stretch)
        self.superchat_view.resizeRowsToContents()
        
    def get_checked_currencies(self):
        checked_currencies = []
        for index in range(self.currencyListWidget.count()):
            if self.currencyListWidget.item(index).checkState() == Qt.Checked:
                checked_currencies.append(self.currencyListWidget.item(index))
        currencylist = [x.text() for x in checked_currencies]
        currencyset = set(currencylist)
        for region in self.curr.keys():
            if region in currencyset:
                #currencyset.remove(region)
                for isocurrency in self.curr[region]:
                    currencyset.add(isocurrency)
            
        return list(currencyset)
    
    def get_checked_chans(self):
        checked_chans = []
        for index in range(self.channelListWidget.count()):
            if self.channelListWidget.item(index).checkState() == Qt.Checked:
                checked_chans.append(self.channelListWidget.item(index))
        chanlist = [x.text() for x in checked_chans]
        return chanlist
        
    def get_supa_time(self,startTime,endTime):
        time_dict = {}
        coord_dict = {}
        area_sums = {}
        #for area in self.curr.keys():
        #    area_sums[area] = [0 for i in range(0,24)]
        self.db.open()
        currencylist = self.get_checked_currencies()
        namelist = self.get_checked_chans()
        names = self.namelist_string(namelist)
        currencies = json.dumps(currencylist).replace("[","(").replace("]",")").replace('"',"'")
        query = QSqlQuery()
        query.prepare("select extract(hour from time_sent AT TIME ZONE 'UTC') as hour, count(distinct user_id) as users, currency, count(*) as donations from messages inner join video v on v.video_id = messages.video_id inner join channel c on c.id = v.channel_id WHERE c.name IN "+names+" and currency in " + currencies + " and time_sent >= :start and time_sent < :end group by currency, extract(hour from time_sent AT TIME ZONE 'UTC') order by hour")
        query.bindValue(":start",startTime)
        query.bindValue(":end",endTime)
        query.exec_()
        while query.next():
            currency = query.value(2).strip()
            usercount = query.value(3)
            hournr = int(query.value(0))
            if currency not in time_dict.keys():
                time_dict[currency] = []
            time_dict[currency].append((time(hour = hournr, tzinfo = timezone.utc),usercount))
            if currency not in coord_dict.keys():
                coord_dict[currency] = {"users":[0 for i in range(0,24)]}
            #coord_dict[query.value(2)]["time"].append(time(hour = int(query.value(0)), tzinfo = timezone.utc))
            coord_dict[currency]["users"][hournr] += usercount
            for area in self.curr.keys():
                if currency in self.curr[area]:
                    if area not in area_sums.keys():
                        area_sums[area] = [0 for i in range(0,24)]
                        #print("empty",area,area_sums[area])
                    area_sums[area][hournr] += usercount
                               
        self.db.close()
        return time_dict, coord_dict, area_sums
        
        
class MySqlModel(QSqlQueryModel):
    def data(self, index, role):
        if not index.isValid():
            return QVariant()
        elif role == Qt.BackgroundRole:
            if index.column() == 1:
                color_s = super().data(index)
                #print(color_s)
                mpl_color = matplotlib.colors.to_rgb(color_s)
                color_q = QColor.fromRgbF(mpl_color[0],mpl_color[1],mpl_color[2])
            else:
                color_q = QColor.fromRgbF(1.0,1.0,1.0)
            return QBrush(color_q)
        elif role != Qt.DisplayRole:
            return QVariant()
        return super().data(index, role)
        
