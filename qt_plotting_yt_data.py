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
import matplotlib.patheffects as path_effects
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
        self.curr = {
                "North America": ["USD","CAD","MXN"],
                "South America": ["ARS","BOB","BRL","CLP","COP","CRC","DOP","GTQ","HNL","NIO","PEN","PYG","UYU"],
                "Europe": ["BAM","BGN","BYN","CHF","CZK","DKK","EUR","GBP","HRK","HUF","ILS","ISK","NOK","PLN","RON","RSD","RUB","SEK","TRY"],
                "Africa": ["ZAR","EGP"],
                "Asia": ["AED","HKD","INR","JOD","JPY","KRW","MYR","PHP","QAR","SAR","SGD","TWD"],
                "Oceania": ["AUD","NZD"]}
        self.pgsql_config_file = open("postgres-config-qt.json")
        self.pgsql_creds = json.load(self.pgsql_config_file)
        self.sc_model = MySqlModel()
        self.populate_widgets()

    def plot_data(self):
        startTime = self.startDateTimeEditor.dateTime()
        endTime = self.endDateTimeEditor.dateTime()
        startTime.setOffsetFromUtc(0)
        endTime.setOffsetFromUtc(0)
        id_list = self.get_checked_chans()
        namelist = self.get_checked_chans(False)
        #print(namelist)
        namelist.sort()
        self.color_dict = self.getcolors(id_list)
        self.color_dict["Europe"] = (0.0,0.0,1.0)
        self.color_dict["North America"] = (1.0,0.0,0.0)
        self.color_dict["Asia"] = (0.0,1.0,0.0)
        self.color_dict["Oceania"] = (0.0,0.0,0.0)
        self.color_dict["Africa"] = (1.0,1.0,0.0)
        self.color_dict["South America"] = (1.0,165/255.0,0.0)
        self.plot_superchat_timing(startTime,endTime)
        stream_dict = {}
        for name in namelist:
            stream_dict[name] = (self.get_stream_sched(startTime,endTime,name))
        heatmap_data, heatmap_sums, streamer_heatmap = self.get_heatmap_data(stream_dict)
        time_dict, coord_dict, area_sums = self.get_supa_time(startTime,endTime)
        self.plot_timetable(stream_dict,startTime,endTime)
        self.plot_heatmap(heatmap_data, self.heatmap_widget)
        self.plot_donor_timing(coord_dict,area_sums)
        self.plot_area_donor_timing(area_sums)
        self.plot_bar_area_donor_timing(self.don_dist_wid,area_sums)
        self.plot_area_donor_per_streamhour(area_sums,heatmap_data)
        tz_friend = self.timezone_friendliness(streamer_heatmap)
        self.fill_tz_friend_tbl(tz_friend)
        return
    
    
    def plot_superchat_timing(self,startTime,endTime):
        datetime_list, date_list, time_list, donation_list = self.get_time_series_data(startTime,endTime)
        self.sc_timing_w.canvas.ax.clear()
        self.sc_timing_w.canvas.ax.set_xlim(startTime.toPyDateTime().date(),endTime.toPyDateTime().date())
        self.sc_timing_w.canvas.ax.scatter(date_list, time_list)
        yFmt = mdates.DateFormatter('%H:%M')
        xFmt = mdates.DateFormatter('%d.%m.%y')
        self.sc_timing_w.canvas.ax.xaxis.set_major_formatter(xFmt)
        self.sc_timing_w.canvas.ax.yaxis.set_major_formatter(yFmt)
        self.sc_timing_w.canvas.ax.set_title("Superchat time")
        self.sc_timing_w.canvas.ax.set_ylabel("Time of day")
        self.sc_timing_w.canvas.ax.set_xlabel("Date")
        self.sc_timing_w.canvas.draw()
        
    def plot_timetable(self,stream_dict,startTime,endTime):
        self.timetable_wid.canvas.ax.clear()
        self.timetable_wid.canvas.ax.set_xlim(startTime.toPyDateTime(),endTime.toPyDateTime())
        self.timetable_wid.canvas.ax.set_ylim(0.0,24.0)
        xFmt = mdates.DateFormatter('%d.%m.%y')
        self.timetable_wid.canvas.ax.xaxis.set_major_formatter(xFmt)
        self.timetable_wid.canvas.ax.set_title("Streaming times")
        self.timetable_wid.canvas.ax.set_ylabel("Time of day")
        self.timetable_wid.canvas.ax.set_xlabel("Date")
        loc = plticker.MultipleLocator(base=2.0) # this locator puts ticks at regular intervals
        patches=[]
        namecount = 0
        for name in stream_dict.keys():
            col = self.choose_color(name)
            patches.append(mpatches.Patch(color=col, label = name))
            for stream in stream_dict[name]:
                time_width = timedelta(days=1) / len(stream_dict.keys())
                stream_date = stream[0].replace(hour=0, minute=0, second=0, microsecond=0)
                x_range = [(stream_date+time_width*namecount,time_width)]
                y_range = (self.time2delta(stream[0].timetz()).seconds/60.0/60.0,stream[1].seconds/60.0/60.0)
                self.timetable_wid.canvas.ax.broken_barh(x_range,y_range, alpha = 0.5, color = col)
            namecount += 1
        days = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
        self.timetable_wid.canvas.ax.yaxis.set_major_locator(loc)
        self.timetable_wid.canvas.ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.15), ncol=3, handles=patches)
        self.timetable_wid.canvas.draw()
        
    def plot_heatmap(self,heatmap_data, widget, ylabels = None):
        days = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']#,'Weekdays','Weekend']
        ylabeling = ylabels if ylabels else days
        widget.canvas.ax.clear()
        widget.canvas.ax2.clear()
        #self.heatmap_widget.canvas.fig.clear()
        widget.canvas.ax.set_title("Stream times heatmap")
        widget.canvas.ax.set_ylabel("Day of week")
        widget.canvas.ax.set_xlabel("Time of day")
        heatmap = plt.pcolor(heatmap_data)
        widget.canvas.fig.colorbar(heatmap,widget.canvas.ax2)
        widget.canvas.ax.imshow(heatmap_data)
        widget.canvas.ax.set_yticks(np.arange(len(ylabeling)))
        widget.canvas.ax.set_yticklabels(ylabeling)
        widget.canvas.ax.set_xticks(np.arange(24))
        for y in range(heatmap_data.shape[0]):
            for x in range(heatmap_data.shape[1]):
                text = widget.canvas.ax.text(x, y, "{:.2f}".format(heatmap_data[y, x]),ha="center", va="center", color="w")
        widget.canvas.draw()
        
    def get_heatmap_data(self,stream_dict):
        heatmap_data = np.zeros((7,24))
        heatmap_sums = np.zeros((3,24))
        streamer_heatmap = {}
        for name in stream_dict.keys():
            streamer_heatmap[name] = np.zeros((10,24))
            for stream in stream_dict[name]:
                stream_hour = stream[0].replace(minute=0, second=0, microsecond=0)
                testtime = stream_hour
                endtime = stream[0] + stream[1]
                #print(stream,testtime,endtime)
                while testtime <= endtime:
                    to_add = 0.0
                    if endtime - testtime < timedelta(hours=1):
                        if endtime - testtime <= timedelta(minutes=5):
                            to_add = 0
                        else:
                            to_add = (endtime - testtime)/timedelta(hours=1)
                    else:
                        to_add = 1.0
                    heatmap_data[testtime.weekday()][testtime.time().hour] += to_add
                    streamer_heatmap[name][testtime.weekday()][testtime.time().hour] += to_add
                    if testtime.weekday() >= 0 and testtime.weekday() <= 4:
                        heatmap_sums[0][testtime.time().hour] += to_add
                        streamer_heatmap[name][7][testtime.time().hour] += to_add
                    elif testtime.weekday() >= 5:
                        heatmap_sums[1][testtime.time().hour] += to_add
                        streamer_heatmap[name][8][testtime.time().hour] += to_add
                    heatmap_sums[2][testtime.time().hour] += to_add
                    streamer_heatmap[name][9][testtime.time().hour] += to_add
                    testtime = testtime + timedelta(hours=1)
        return heatmap_data, heatmap_sums, streamer_heatmap
        
    def plot_donor_timing(self, coord_dict, area_sums):
        #xFmt = mdates.DateFormatter('%H:%M')
        loc = plticker.MultipleLocator(base=2.0)
        self.donortiming.canvas.ax.clear()
        self.donortiming.canvas.ax.set_title("Donors per currency at which time")
        self.donortiming.canvas.ax.xaxis.set_major_locator(loc)
        #self.donortiming.canvas.ax.xaxis.set_major_formatter(xFmt)
        self.donortiming.canvas.ax.set_ylabel("amount of unique superchatters")
        self.donortiming.canvas.ax.set_xlabel("Time of day")
        for currency in coord_dict:
            self.donortiming.canvas.ax.plot(coord_dict[currency]["users"],label = currency, color = self.choose_color(currency), linewidth = 4)
        self.donortiming.canvas.ax.legend(loc="right")
        self.donortiming.canvas.draw()
        return
    
    def plot_area_donor_timing(self,area_sums):
        self.area_sc_timing_draw.canvas.ax.clear()
        loc = plticker.MultipleLocator(base=2.0)
        self.area_sc_timing_draw.canvas.ax.xaxis.set_major_locator(loc)
        self.area_sc_timing_draw.canvas.ax.set_title("Donors per region at which time")
        self.area_sc_timing_draw.canvas.ax.set_ylabel("amount of unique superchatters")
        self.area_sc_timing_draw.canvas.ax.set_xlabel("Time of day")
        for area in area_sums.keys():
            self.area_sc_timing_draw.canvas.ax.plot(area_sums[area], label = str(area), color = self.choose_color(area), linewidth = 4)
        self.area_sc_timing_draw.canvas.ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.15), ncol=3)
        self.area_sc_timing_draw.canvas.draw()
        return
    
    def plot_bar_area_donor_timing(self,widget,area_sums):
        idx = np.arange(24)
        width = 0.5
        widget.canvas.ax.clear()
        loc = plticker.MultipleLocator(base=1.0)
        widget.canvas.ax.xaxis.set_major_locator(loc)
        widget.canvas.ax.set_title("Donors per region at which time")
        widget.canvas.ax.set_ylabel("percentage of unique superchatters")
        widget.canvas.ax.set_xlabel("Time of day")
        chartlist = []
        areas = ["North America","South America","Europe","Africa","Asia","Oceania"]
        areas.reverse()
        donorsum = np.zeros(24)
        for areano in range(0,len(areas)):
            donorsum = np.add(donorsum,area_sums[areas[areano]])
        #print("donorsum",donorsum)
        areapercents = {}
        areacum = {}
        area_sum = np.asarray(area_sums[areas[0]])
        percentages = np.divide(area_sum,donorsum, out=np.zeros_like(donorsum), where=donorsum!=0)
        areapercents[areas[0]] = percentages
        areacum[areas[0]] = np.add(percentages,[0 for i in range(0,24)])
        chartlist.append(widget.canvas.ax.bar(idx, percentages, width, label=areas[0], color = self.choose_color(areas[0])))
        for areano in range(1,len(areas)):
            area_sum = np.asarray(area_sums[areas[areano]])
            percentages = np.divide(area_sum,donorsum,out=np.zeros_like(donorsum), where=donorsum!=0)
            areapercents[areas[areano]] = percentages
            bottomsum = np.zeros(24)
            for n in range(0,areano):
                bottomsum = np.add(bottomsum,area_sums[areas[n]])
            bottomper = np.divide(bottomsum, donorsum,out=np.zeros_like(bottomsum), where=donorsum!=0)
            #print(bottomper)
            areacum[areas[areano]] = np.add(percentages,bottomper)
            chartlist.append(widget.canvas.ax.bar(idx, percentages, width, label=areas[areano], color = self.choose_color(areas[areano]), bottom = bottomper))
        #print(areapercents,areacum)
        for n in idx:
            for area in areas:
                proportion, y_loc, count = (areapercents[area][n], areacum[area][n], area_sums[area][n])
                if count > 0 and proportion > 0.02:
                    txt = widget.canvas.ax.text(x=n - 0.25,
                         y=(y_loc - proportion) + (proportion / 2),
                         s=f'{count}\n({int(np.round(proportion * 100, 0))}%)', 
                         color="white",
                         fontsize=10,
                         fontweight="bold")
                    txt.set_path_effects([path_effects.Stroke(linewidth=3, foreground='black'),
                       path_effects.Normal()])
        widget.canvas.ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.15), ncol=3)
        widget.canvas.ax.yaxis.set_major_formatter(plticker.PercentFormatter(1.0)) 
        widget.canvas.draw()
        return
    
    def plot_area_donor_per_streamhour(self,area_sums,heatmap_data):
        streamhours = np.zeros(24)
        for day in heatmap_data:
            streamhours = streamhours + day
        #print("streamhours",streamhours)
        self.area_strhour_sc_wid.canvas.ax.clear()
        loc = plticker.MultipleLocator(base=2.0)
        self.area_strhour_sc_wid.canvas.ax.xaxis.set_major_locator(loc)
        self.area_strhour_sc_wid.canvas.ax.set_title("Donors per region at which time per running stream")
        self.area_strhour_sc_wid.canvas.ax.set_ylabel("amount of average unique superchatters")
        self.area_strhour_sc_wid.canvas.ax.set_xlabel("Time of day")
        for area in area_sums.keys():
            #print(area,area_sums[area])
            area_avg = np.divide(np.asarray(area_sums[area]),streamhours,out=np.zeros_like(streamhours), where=streamhours!=0)
            self.area_strhour_sc_wid.canvas.ax.plot(area_avg, label = str(area), color = self.choose_color(area), linewidth = 4)
        self.area_strhour_sc_wid.canvas.ax.plot(streamhours, label = "Streamhours offered", color = self.choose_color("total"), linewidth = 4)
        self.area_strhour_sc_wid.canvas.ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.15), ncol=4)
        self.area_strhour_sc_wid.canvas.draw()
        return
    
    def fill_tz_friend_tbl(self, data):
        row_list = []
        for streamer, tzfriend in data.items():
            for tz, friend in tzfriend.items():
                row_list.append([streamer,tz,friend])
        table = self.tz_friend_table
        table.setRowCount(0)
        table.setColumnCount(3)
        table.setRowCount(len(row_list))
        table.setHorizontalHeaderLabels(["Streamer", "Timezone", "Friendliness"])
        for y in range(len(row_list)):
            table.setItem(y, 0, QTableWidgetItem(row_list[y][0]))
            table.setItem(y, 1, QTableWidgetItem(row_list[y][1]))
            table.setItem(y, 2, QTableWidgetItem("{:.2%}".format(row_list[y][2])))
        table.resizeColumnsToContents()
        table.resizeRowsToContents()

    
    def populate_widgets(self):
        self.db = QSqlDatabase.addDatabase('QPSQL')
        self.db.setHostName(self.pgsql_creds["host"])
        self.db.setUserName(self.pgsql_creds["username"])
        self.db.setPassword(self.pgsql_creds["password"])
        self.db.setDatabaseName(self.pgsql_creds["database"])
        self.db.open()
        query = QSqlQuery()
        print("querying names")
        query.exec_("select name, id from channel inner join video v on id = v.channel_id group by id order by name")
        while query.next():
            #print(query.value(0))
            #print(query.value(1))
            entry = QListWidgetItem(query.value(0).strip())
            entry.setData(32,query.value(1))
            entry.setCheckState(Qt.Unchecked)
            self.channelListWidget.addItem(entry)
        print("querying currencies")
        query.exec_("select currency from messages where currency <> 'MON' group by currency order by currency")
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
        query.prepare("select color, id, name from channel where id in "+names+" and color is not null")
        query.exec_()
        while query.next():
            h = "#"+query.value(0)
            db_color = matplotlib.colors.to_rgb(h)
            color_dict[query.value(2)] = db_color
        self.db.close()
        return color_dict
    
    def get_stream_sched(self,startTime,endTime,name):
        stream_list = []
        stream_list = stream_list + self.get_past_schedule(startTime,endTime,name)
        stream_list_new = []
        for stream in stream_list:
                stream_list_new = stream_list_new + self.check_midnight(stream[0],stream[1])
        return stream_list_new
    
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
            plannedstarttime = query.value(2).toPyDateTime() if query.value(2) else None
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
                #print("#",starttime,duration,end_time,vid)
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
        #query.prepare("SELECT time_sent AT TIME ZONE 'UTC', extract(hour from time_sent AT TIME ZONE 'UTC') as hour, extract(minute from time_sent AT TIME ZONE 'UTC') as minute, currency, value from messages inner join video v on v.video_id = messages.video_id inner join channel c on c.id = v.channel_id WHERE c.name IN "+names+" and currency in "+currencies+" and time_sent >= :start and time_sent < :end ORDER BY hour")
        query.prepare("SELECT time_sent AT TIME ZONE 'UTC', extract(hour from time_sent AT TIME ZONE 'UTC') as hour, extract(minute from time_sent AT TIME ZONE 'UTC') as minute, currency, value from messages inner join video v on v.video_id = messages.video_id WHERE v.channel_id IN "+names+" and currency in "+currencies+" and time_sent >= :start and time_sent < :end ORDER BY hour")
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
        #test = query.prepare("SELECT video_id, title, scheduledStartTime AT TIME ZONE 'UTC' from video inner join channel c on c.id = video.channel_id WHERE c.name IN "+names+" and scheduledStartTime >= :start and scheduledStartTime < :end ORDER BY scheduledStartTime")
        test = query.prepare("SELECT video_id, title, scheduledStartTime AT TIME ZONE 'UTC' from video WHERE video.channel_id IN "+names+" and scheduledStartTime >= :start and scheduledStartTime < :end ORDER BY scheduledStartTime")
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
    
    def get_checked_chans(self, id = True):
        checked_chans = []
        for index in range(self.channelListWidget.count()):
            if self.channelListWidget.item(index).checkState() == Qt.Checked:
                checked_chans.append(self.channelListWidget.item(index))
        if id:
            chanlist = [x.data(32) for x in checked_chans]
        else:
            chanlist = [x.text() for x in checked_chans]
        return chanlist
        
    def get_supa_time(self,startTime,endTime):
        time_dict = {}
        coord_dict = {}
        area_sums = {}
        for area in self.curr.keys():
            area_sums[area] = [0 for i in range(0,24)]
        self.db.open()
        currencylist = self.get_checked_currencies()
        namelist = self.get_checked_chans()
        names = self.namelist_string(namelist)
        currencies = json.dumps(currencylist).replace("[","(").replace("]",")").replace('"',"'")
        query = QSqlQuery()
        #query.prepare("select extract(hour from time_sent AT TIME ZONE 'UTC') as hour, count(distinct user_id) as users, currency, count(*) as donations from messages inner join video v on v.video_id = messages.video_id inner join channel c on c.id = v.channel_id WHERE c.name IN "+names+" and currency in " + currencies + " and time_sent >= :start and time_sent < :end group by currency, extract(hour from time_sent AT TIME ZONE 'UTC') order by hour")
        query.prepare("select extract(hour from time_sent AT TIME ZONE 'UTC') as hour, count(distinct user_id) as users, currency, count(*) as donations from messages inner join video v on v.video_id = messages.video_id WHERE v.channel_id IN "+names+" and currency in " + currencies + " and time_sent >= :start and time_sent < :end group by currency, extract(hour from time_sent AT TIME ZONE 'UTC') order by hour")
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
                #if area not in area_sums.keys():
                    #area_sums[area] = [0 for i in range(0,24)]
                if currency in self.curr[area]:
                    area_sums[area][hournr] += usercount
                               
        self.db.close()
        return time_dict, coord_dict, area_sums
    
    def timezone_friendliness(self,streamer_heatmap):
        friend_time = self.generate_friendliness_mtx()
        friendlyindex = {}
        for streamer, heatmap in streamer_heatmap.items():
            shaved_map = np.delete(heatmap,[7,8,9],0)
            streamedhrs = shaved_map.sum()
            timezone_friend = {}
            for tz, idealtime in friend_time.items():
                friendlyhrs = np.multiply(shaved_map,idealtime).sum()
                friendlyperc = friendlyhrs / streamedhrs
                timezone_friend[tz] = friendlyperc
            friendlyindex[streamer] = timezone_friend
        print(friendlyindex)
        return friendlyindex
    
    def generate_friendliness_mtx(self):
        timezones = [pytz.timezone("Asia/Tokyo"),pytz.timezone("Asia/Jakarta"),pytz.timezone("Europe/Moscow"),pytz.timezone("Europe/Berlin"),pytz.timezone("US/Eastern"),pytz.timezone("US/Pacific")]
        friendly_timeframes = {}
        for zone in timezones:
            watch_start = [zone.localize(datetime(2000,1,1,hour=18)),zone.localize(datetime(2000,1,1,hour=18)),zone.localize(datetime(2000,1,1,hour=18)),zone.localize(datetime(2000,1,1,hour=18)),zone.localize(datetime(2000,1,1,hour=18)),zone.localize(datetime(2000,1,1,hour=14)),zone.localize(datetime(2000,1,1,hour=14))]
            watch_end = [zone.localize(datetime(2000,1,2,hour=0)),zone.localize(datetime(2000,1,2,hour=0)),zone.localize(datetime(2000,1,2,hour=0)),zone.localize(datetime(2000,1,2,hour=0)),zone.localize(datetime(2000,1,2,hour=2)),zone.localize(datetime(2000,1,2,hour=2)),zone.localize(datetime(2000,1,2,hour=0))]
            timeframe = np.zeros((7,24))
            days_p = 0
            for start, end in zip(watch_start, watch_end):
                dur = end-start
                start_utc = start.astimezone(pytz.utc)
                testtime = start_utc
                endtime = end.astimezone(pytz.utc)
                while testtime <= endtime:
                    to_add = 0.0
                    if endtime - testtime < timedelta(hours=1):
                        if endtime - testtime <= timedelta(minutes=5):
                            to_add = 0
                        else:
                            to_add = (endtime - testtime)/timedelta(hours=1)
                    else:
                        to_add = 1.0
                    timeframe[(testtime.day-1+days_p)%7][testtime.time().hour] += to_add
                    testtime = testtime + timedelta(hours=1)
                days_p += 1
            friendly_timeframes[watch_start[0].tzname()] = timeframe
        #print(friendly_timeframes)
        return friendly_timeframes
        
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
        
