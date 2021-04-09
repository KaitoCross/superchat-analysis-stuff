import os, pathlib, json, argparse, time, typing, math
from datetime import datetime, date, timedelta, timezone
from forex_python.converter import CurrencyRates, RatesNotAvailableError
from os import listdir
from os.path import isfile, join
import csv

def writeCsvFile(fname, data, *args, **kwargs):
	mycsv = csv.writer(open(fname, 'w'), *args, **kwargs)
	for row in data:
		mycsv.writerow(row)
		
def round_up(a, threshold):
    if a - int(a) >= threshold:
        return int(a) + 1
    return int(a)

parser = argparse.ArgumentParser()
parser.add_argument('yt_channel_id', metavar='N', type=str, help='The YouTube channel ID')
args = parser.parse_args()

big_sc_log = []
file_logs = []
sc_per_stream={}

date_currencies={}
currencies = set()

logpath = args.yt_channel_id+"/sc_logs"
statpath =  args.yt_channel_id+"/vid_stats"
sc_log_files = [f for f in listdir(logpath) if isfile(join(logpath, f))]
stat_files = [f for f in listdir(statpath) if isfile(join(statpath, f))]

for i in range(8):
	x = [None]*24
	big_sc_log.append(x)

#print(big_sc_log)
stream_metadata={}

ref_currency = "EUR"

for day in range(8):
			for hour in range(24):
				big_sc_log[day][hour] = {}
				big_sc_log[day][hour].setdefault("amountStreams",0)

for file in stat_files:
	#print(file)
	id = file.split('_stats.')[0]
	statfile = open(statpath+"/"+file,"r")
	content = statfile.read()
	statfile.close()
	try:
		stream_metadata[id] = json.loads(content)
		if isinstance(stream_metadata[id][0]["liveStreamingDetails"]["actualStartTime"], list):
			#print("am list")
			start_time = stream_metadata[id][0]["liveStreamingDetails"]["actualStartTime"][0]
		else:
			start_time = stream_metadata[id][0]["liveStreamingDetails"]["actualStartTime"]
		if isinstance(stream_metadata[id][0]["liveStreamingDetails"]["actualEndTime"], list):
			end_time = stream_metadata[id][0]["liveStreamingDetails"]["actualEndTime"][0]
		else:
			end_time = stream_metadata[id][0]["liveStreamingDetails"]["actualEndTime"]
		#print("End time", end_time)
		#print(start_time)
		start_dt = datetime.fromtimestamp(start_time,timezone.utc)
		end_dt = datetime.fromtimestamp(end_time,timezone.utc)
		real_duration = end_dt - start_dt
		covered_hours = real_duration + timedelta(minutes = start_dt.minute)
		amount_covered_hrs = (covered_hours.seconds + covered_hours.days*86400)/60.0/60.0
		amount_covered_hrs = round_up(amount_covered_hrs,10/60)
		print(start_dt, end_dt)
		for hours in range(start_dt.hour,start_dt.hour+amount_covered_hrs):
			#print(start_dt, end_dt)
			big_sc_log[(start_dt.weekday()+math.floor(hours/24))%7][hours%24]["amountStreams"] += 1
			print((start_dt.weekday()+math.floor(hours/24))%7,hours%24, big_sc_log[(start_dt.weekday()+math.floor(hours/24))%7][hours%24]["amountStreams"])
			print(big_sc_log[(start_dt.weekday()+math.floor(hours/24))%7][hours%24]["amountStreams"])
		
	except Exception as e:
		print("something failed", file)
		print(e)
		continue


for file in sc_log_files:
	id = file.split('.')[0]
	logfile = open(logpath+"/"+file)
	content = logfile.read()
	try:
		logs = json.loads(content)
	except:
		continue
	for dict in logs:
		the_currency = dict["currency"]
		date_d = datetime.fromtimestamp(dict['time']/1000.0,timezone.utc).date()#date.fromtimestamp()
		date_s = date_d.isoformat()
		#print(date_s,the_currency)
		dict['videoId'] = id
		dict['isodate'] = date_s
		dict['date'] = date_d
		file_logs.append(dict)
		if date_s not in date_currencies.keys():
			date_currencies[date_s] = {}
		date_currencies[date_s][the_currency] = True
		#print(date_currencies)
		currencies.add(the_currency)

#c = CurrencyRates()
#for date_s in date_currencies.keys():
	#print("fetching conversion rates from",date_s)
	#for currency in date_currencies[date_s].keys():
		#date_d = date.fromisoformat(date_s)
		#print(currency, date_s)
		#try:
			#date_currencies[date_s][currency] = 0#c.get_rate(currency,ref_currency,datetime(date_d.year,date_d.month,date_d.day))
		#except RatesNotAvailableError as e:
			#date_currencies[date_s][currency] = 0
		#print(date_currencies[date_s][currency])
		#time.sleep(0.1)

for logentry in file_logs:
	#print(logentry["weekday"])
	weekday = logentry["weekday"]
	hour = logentry["hour"]
	currency = logentry["currency"]
	date_s = logentry["isodate"]
	value = logentry["value"]
	if logentry["videoId"] not in sc_per_stream.keys():
		sc_per_stream[logentry["videoId"]] = 1
	else:
		sc_per_stream[logentry["videoId"]] += 1
	if big_sc_log[weekday][hour] is None:
		big_sc_log[weekday][hour] = {}
	if currency not in big_sc_log[weekday][hour].keys():
		big_sc_log[weekday][hour][currency] = {"value":value,
											   #"converted": value * date_currencies[date_s][currency],
											   "count_sc": 1}
	else:
		big_sc_log[weekday][hour][currency]['value'] += value
		#big_sc_log[weekday][hour][currency]['converted'] += (value * date_currencies[date_s][currency])
		big_sc_log[weekday][hour][currency]['count_sc'] += 1
	if weekday < 5:
		if big_sc_log[7][hour] is None:
			big_sc_log[7][hour] = {}
			#print("Am I a joke to you")
		if currency not in big_sc_log[7][hour].keys():
			big_sc_log[7][hour][currency] = {'value': value, 'count_sc': 1}#, "converted": value * date_currencies[date_s][currency]}
		else:
			big_sc_log[7][hour][currency]['value'] += value
			big_sc_log[7][hour][currency]['count_sc'] += 1
			#big_sc_log[7][hour][currency]['converted'] += (value * date_currencies[date_s][currency])
		
#print(big_sc_log[7])


sc_stat_tables = []
for day in big_sc_log:
	currencyList = list(currencies)
	currencyList.insert(0,"hour of day")
	currencyList.append("STREAMS")
	hours_currency = []
	hours_currency.append(currencyList)
	hours_sc_amount = []
	hours_sc_amount.append(currencyList)
	hour_nr = 0
	for hour in day:
		currencies_in_hour = []
		currency_sc_in_hour = []
		for currency in currencyList:
			if hour is None:
				hour = {}
			if currency in hour.keys():
				currencies_in_hour.append(hour[currency]["value"])
				currency_sc_in_hour.append(hour[currency]["count_sc"])
			elif currency == "STREAMS":
				currencies_in_hour.append(hour["amountStreams"])
				currency_sc_in_hour.append(hour["amountStreams"])
			elif currency == "hour of day":
				currencies_in_hour.append(hour_nr)
				currency_sc_in_hour.append(hour_nr)
				hour_nr += 1
			else:
				currencies_in_hour.append(0)
				currency_sc_in_hour.append(0)
		hours_currency.append(currencies_in_hour)
		hours_sc_amount.append(currency_sc_in_hour)
	sc_stat_tables.append(hours_currency+hours_sc_amount)
	
#print(sc_stat_tables)
for i in range(8):
	#print("Tag Nr.",i)
	#print(sc_stat_tables[i])
	filename = args.yt_channel_id+"/day"+str(i)+".csv"
	writeCsvFile(filename,sc_stat_tables[i])

#print(sc_per_stream)

for file in stat_files:
	#print(file)
	id = file.split('_stats.')[0]
	if id in sc_per_stream.keys():
		statfile = open(statpath+"/"+file,"r+")
		content = statfile.read()
		try:
			stats = json.loads(content)
		except Exception as e:
			print(file)
			print(e)
			continue
		stats[0]["sc_amount"] = sc_per_stream[id]
		statfile.seek(0)
		statfile.write(json.dumps(stats))
		statfile.truncate()
	statfile.close()