# -*- coding: utf-8 -*-
import asyncio, pytz, argparse, time, os, functools, json, isodate, pathlib, concurrent.futures, asyncpg, copy, logging, httpx
from datetime import datetime, timezone, timedelta
from concurrent.futures import CancelledError
from pytchat import (LiveChatAsync, SuperchatCalculator, SuperChatLogProcessor,config)
from youtube_api import YouTubeDataAPI
from sc_wordcloud import superchat_wordcloud
from merge_SC_logs_v2 import recount_money
from decimal import Decimal

class SuperchatArchiver:
    def __init__(self,vid_id, api_key, gen_WC = False, loop = None, file_suffix = ".standalone.txt", minutes_wait = 30):
        self.total_counted_msgs = 0
        self.max_retry_attempts = 48 + 24
        self.file_suffix = file_suffix
        self.minutes_wait = minutes_wait
        self.started_at = None
        self.ended_at = None
        self.cancelled = False
        self.loop = loop
        self.t_pool = concurrent.futures.ThreadPoolExecutor(max_workers=100)
        self.api_points_used = 1.0
        self.api = YouTubeDataAPI(api_key) #uses 1p to check key
        self.videoid = vid_id
        self.channel_id = ""
        self.metadata = {}
        self.videoinfo = {}
        self.donors = {}
        self.stats = []
        self.sc_msgs = set()
        self.sc_logs_list = []
        self.metadata_list = []
        self.gen_wc = gen_WC
        self.unique_donors = {}
        self.clean_currency = {"¥": "JPY",
                          "NT$": "TWD",
                          "$": "USD",
                          "CA$": "CAD",
                          "MX$": "MXN",
                          "HK$": "HKD",
                          "A$": "AUD",
                          "£": "GBP",
                          "€": "EUR",
                          "R$": "BRL",
                          "₹": "INR",
                          "\u20b1": "PHP",
                          "\u20aa": "ILS"}

        self.metadata = self.get_video_info(self.videoid)
        self.api_points_used += 1.0
        self.running = True
        self.running_chat = None
        if self.metadata is not None:
            self.videoinfo = self.metadata
            self.videoinfo["retries_of_rerecording_had_scs"] = 0
            self.videoinfo["retries_of_rerecording"] = 0
            self.videoPostedAt = copy.deepcopy(self.videoinfo["publishDateTime"])
            self.channel_id = self.metadata["channelId"]
        else:
            self.videoPostedAt = 0
            self.channel_id = ""
        self.skeleton_dict = {"channel": None,
                              "channelId": None,
                              "id": None,
                              "title": None,
                              "live": None,
                              "caught_while": None,
                              "publishDateTime": None,
                              "length": None,
                              "endedLogAt": None,
                              "retries_of_rerecording": None,
                              "retries_of_rerecording_had_scs": None,
                              "createdDateTime": None,
                              "liveStreamingDetails":{"scheduledStartTime": None,
                                                      "actualStartTime": None,
                                                      "actualEndTime": None}
                             }
        self.sc_file = self.channel_id + "/sc_logs/" + self.videoid + ".txt"+self.file_suffix
        self.donor_file = self.channel_id + "/vid_stats/donors/" + self.videoid + ".txt"+self.file_suffix
        self.stats_file = self.channel_id + "/vid_stats/" + self.videoid + "_stats.txt"+self.file_suffix
        print(self.metadata, self.channel_id, self.videoid, self.file_suffix)
        pathlib.Path('./' + self.channel_id + '/vid_stats/donors').mkdir(parents=True, exist_ok=True)
        pathlib.Path('./' + self.channel_id + '/sc_logs').mkdir(parents=True, exist_ok=True)
        self.placeholders = 0

    def __str__(self):
        return "["+self.videoid+"] " + self.videoinfo["channel"] + " - " + self.videoinfo["title"] + " - Running: "+str(self.running)
    
    def __repr__(self):
        return "["+self.videoid+"] " + self.videoinfo["channel"] + " - " + self.videoinfo["title"] + " - Running: "+str(self.running)

    def get_video_info(self,video_ID:str):
        response = None
        try:
            response = self.api.get_video_metadata(video_id=video_ID, parser=None,
                                                   part=["liveStreamingDetails", "contentDetails", "snippet"])
            api_metadata = {"channel": response["snippet"]["channelTitle"],
                            "channelId": response["snippet"]["channelId"],
                            "id": video_ID,
                            "title": response["snippet"]["title"],
                            "live": response["snippet"]["liveBroadcastContent"],
                            "caught_while": response["snippet"]["liveBroadcastContent"],
                            "publishDateTime": datetime.strptime(response["snippet"]["publishedAt"] + " +0000",
                                                                 "%Y-%m-%dT%H:%M:%SZ %z").timestamp()}
            delta = isodate.parse_duration(response["contentDetails"]["duration"])
            api_metadata["length"] = delta.total_seconds()
            if 'liveStreamingDetails' in response.keys():
                api_metadata["liveStreamingDetails"] = {}
                for d in response["liveStreamingDetails"].keys():
                    if "Time" in d or "time" in d:
                        api_metadata["liveStreamingDetails"][d] = datetime.strptime(
                            response["liveStreamingDetails"][d] + " +0000", "%Y-%m-%dT%H:%M:%SZ %z").timestamp()
            return api_metadata

        except Exception as e:
            print(self.videoid)
            print(e)
            print(response)
            return None

    async def async_get_video_info(self,video_ID:str):
        self.api_points_used += 1.0
        api_metadata = await self.loop.run_in_executor(self.t_pool,self.get_video_info,video_ID)
        return api_metadata

    def cancel(self):
        self.cancelled = True
        if self.running_chat:
            self.running_chat.terminate()
        

    async def update_psql_metadata(self):
        async with self.conn.transaction():
            await self.conn.execute(
                "UPDATE video SET caught_while = $2, live = $3, title = $4,"
                "retries_of_rerecording = $5, retries_of_rerecording_had_scs = $6 WHERE video_id = $1",
                self.videoid, self.videoinfo["caught_while"], self.videoinfo["live"],
                self.videoinfo["title"], self.videoinfo["retries_of_rerecording"],
                self.videoinfo["retries_of_rerecording_had_scs"])
            if "scheduledStartTime" in self.videoinfo["liveStreamingDetails"].keys():
                await self.conn.execute("UPDATE video SET scheduledstarttime = $2 WHERE video_id = $1",
                                        self.videoid, datetime.fromtimestamp(
                        self.videoinfo["liveStreamingDetails"]["scheduledStartTime"], timezone.utc))
            if "actualStartTime" in self.videoinfo["liveStreamingDetails"].keys():
                await self.conn.execute("UPDATE video SET actualstarttime = $2 WHERE video_id = $1",
                                        self.videoid, datetime.fromtimestamp(
                        self.videoinfo["liveStreamingDetails"]["actualStartTime"], timezone.utc))
            if "actualEndTime" in self.videoinfo["liveStreamingDetails"].keys():
                await self.conn.execute("UPDATE video SET actualendtime = $2 WHERE video_id = $1",
                                        self.videoid, datetime.fromtimestamp(
                        self.videoinfo["liveStreamingDetails"]["actualEndTime"], timezone.utc))
            if "old_title" in self.videoinfo.keys():
                await self.conn.execute("UPDATE video SET old_title = $2 WHERE  video_id = $1", self.videoid,
                                        self.videoinfo["old_title"])
            if "length" in self.videoinfo.keys():
                await self.conn.execute("UPDATE video SET length = $2 WHERE  video_id = $1", self.videoid,
                                        self.videoinfo["length"])
            if "publishDateTime" in self.videoinfo.keys():
                await self.conn.execute("UPDATE video SET publishDateTime = $2 WHERE video_id = $1",
                                        self.videoid, datetime.fromtimestamp(self.videoinfo["publishDateTime"],
                                                                             timezone.utc))
            if "endedLogAt" in self.videoinfo.keys():
                await self.conn.execute("UPDATE video SET endedLogAt = $2 WHERE video_id = $1",
                                        self.videoid, self.ended_at)
                
    async def already_done(self,conn):
        row = await conn.fetchrow('SELECT retries_of_rerecording_had_scs FROM video WHERE video_id = $1', self.videoid)
        successful_sc_recordings = row["retries_of_rerecording_had_scs"] if row else 0
        test_file = pathlib.Path(self.sc_file)
        if test_file.is_file():
            if test_file.stat().st_size > 2:
                file_has_content = True
        if successful_sc_recordings >= 2 and file_has_content:
            return True, test_file.stat().st_size, successful_sc_recordings
        else:
            return False, 0, successful_sc_recordings

    async def main(self):
        if not self.loop:
            self.loop = asyncio.get_running_loop()
        pgsql_config_file = open("postgres-config.json")
        pgsql_creds = json.load(pgsql_config_file)
        self.conn = await asyncpg.connect(user = pgsql_creds["username"], password = pgsql_creds["password"], host = pgsql_creds["host"], database = pgsql_creds["database"])
        old_meta_row = await self.conn.fetchrow('SELECT c.name, channel_id, title, caught_while, live, old_title, length, createdDateTime, publishDateTime, startedLogAt, endedLogAt, scheduledStartTime, actualStartTime, actualEndTime, retries_of_rerecording, retries_of_rerecording_had_scs FROM video INNER JOIN channel c on channel_id = c.id WHERE video_id = $1', self.videoid)
        old_meta = dict(old_meta_row) if old_meta_row else None
        if old_meta:
            old_time_meta = {"scheduledStartTime": old_meta["scheduledstarttime"].timestamp() if old_meta["scheduledstarttime"] else 0,
                             "actualStartTime": old_meta["actualstarttime"].timestamp() if old_meta["actualstarttime"] else 0,
                             "actualEndTime": old_meta["actualendtime"].timestamp() if old_meta["actualendtime"] else 0}
            old_meta["liveStreamingDetails"] = old_time_meta
            if not self.videoinfo:
                self.videoinfo = copy.deepcopy(self.skeleton_dict)
            if self.videoinfo["title"] != old_meta["title"] and self.videoinfo["title"]:
                old_meta["old_title"] = old_meta["title"]
                old_meta["title"] = self.videoinfo["title"]
            old_meta_keys_l = [k.lower() for k in old_meta.keys()]
            old_meta_keys_n = [k for k in old_meta.keys()]
            old_meta_keys = dict(zip(old_meta_keys_l, old_meta_keys_n))
            print(old_meta_keys)
            for info in self.skeleton_dict.keys():
                if info.lower() in old_meta_keys_l:
                    if type(old_meta[old_meta_keys[info.lower()]]) is datetime:
                        self.videoinfo[info] = old_meta[old_meta_keys[info.lower()]].timestamp()
                    elif old_meta[old_meta_keys[info.lower()]]:
                        self.videoinfo[info] = old_meta[old_meta_keys[info.lower()]]
                    elif not old_meta[old_meta_keys[info.lower()]] and "time" in info.lower():
                        self.videoinfo[info] = 0
                    else:
                        self.videoinfo[info] = None
            self.channel_id = old_meta["channel_id"]
            self.videoinfo["channel"] = old_meta["name"]
            self.videoPostedAt = self.videoinfo['publishDateTime']
                        
        if not self.videoinfo:
            await self.conn.close()
            return
        self.insert_channels = await self.conn.prepare("INSERT INTO channel(id, name, tracked) VALUES ($1,$2,$3) "
                                                       "ON CONFLICT DO NOTHING")
        self.channel_name_history = await self.conn.prepare("INSERT INTO chan_names(id, name, time_discovered) "
                                                            "VALUES ($1,$2,$3) ON CONFLICT DO NOTHING")
        self.insert_messages = await self.conn.prepare("INSERT INTO messages(video_id, user_id, message_txt, "
                                                       "time_sent, currency, value, color) "
                                                       "VALUES ($1,$2,$3,$4,$5,$6,$7) ON CONFLICT DO NOTHING")
        async with self.conn.transaction():
            if self.channel_id and self.videoinfo["channel"]:
                await self.conn.execute("INSERT INTO channel VALUES($1,$2,$3) ON CONFLICT DO NOTHING",
                                       self.channel_id, self.videoinfo["channel"], True)
                await self.conn.execute("INSERT INTO chan_names VALUES($1,$2,$3) ON CONFLICT DO NOTHING",
                                        self.channel_id, self.videoinfo["channel"],
                                        datetime.now(tz=pytz.timezone('Europe/Berlin')))
        self.chat_err = True
        repeats = 0
        log_exist_test, filesize, db_retries_had_scs = await self.already_done(self.conn)
        if log_exist_test:
            await self.log_output(self.videoinfo["channel"] + " - " + self.videoinfo[
                    "title"] + " already analyzed, skipping. Existing file size: " + str(
                    filesize) + " bytes")
            return
        had_scs = db_retries_had_scs if db_retries_had_scs else 0
        self.msg_counter = 0
        caughtlive = True
        while (repeats < self.max_retry_attempts and had_scs < 2 and not self.cancelled and caughtlive):
            self.msg_counter = 0
            self.chat_err = True
            while self.chat_err and not self.cancelled:
                if "liveStreamingDetails" in self.videoinfo.keys() or self.videoinfo["live"] != "none" or repeats >= 1:
                    self.stats.clear()
                    self.chat_err = False
                    self.started_at = datetime.now(tz=pytz.timezone('Europe/Berlin'))
                    publishtime = datetime.fromtimestamp(self.videoPostedAt,timezone.utc)
                    async with self.conn.transaction():
                        await self.conn.execute(
                            "INSERT INTO video (video_id,channel_id,title,startedlogat,createddatetime) "
                            "VALUES($1,$2,$3,$4,$5) ON CONFLICT DO NOTHING",
                            self.videoid, self.videoinfo["channelId"], self.videoinfo["title"], self.started_at, publishtime)
                    await self.update_psql_metadata()
                    await self.log_output("Started Analysis #"+str(repeats+1)+" at: "+self.started_at.isoformat())
                    await self.log_output("of video " + publishtime.isoformat() + " " +self.videoinfo["channel"]+" - " + self.videoinfo["title"] + " ["+self.videoid+"]")
                    if repeats >= 1:
                        await self.log_output("Recording the YouTube-archived chat after livestream finished")
                    self.httpclient = httpx.AsyncClient(http2=True)
                    self.running_chat = LiveChatAsync(self.videoid, callback = self.display, processor = (SuperChatLogProcessor(), SuperchatCalculator()),logger=config.logger(__name__,logging.DEBUG), client = self.httpclient)
                    while self.running_chat.is_alive() and not self.cancelled:
                        await asyncio.sleep(3)
                    if repeats == 0 and not self.chat_err:
                        self.ended_at = datetime.now(tz=pytz.timezone('Europe/Berlin'))
                        self.videoinfo["endedLogAt"] = self.ended_at.timestamp()
                    await self.httpclient.aclose()
                    newmetadata = await self.async_get_video_info(self.videoid) #when livestream chat parsing ends, get some more metadata
                    if newmetadata is not None:
                        if newmetadata["live"] in ["upcoming","live"]: #in case the livestream has not ended yet!
                            await self.log_output(datetime.now(tz=pytz.timezone('Europe/Berlin')).isoformat()+": Error! Chat monitor ended prematurely!")
                            await self.log_output(self.running_chat.is_alive())
                            self.chat_err = True
                    if self.videoinfo["caught_while"] in ["upcoming","live"]:
                        #use newer metadata while rescuing certain fields from the old metadata
                        createdDateTime = self.videoPostedAt
                        caught_while = self.videoinfo["caught_while"]
                        old_title = self.videoinfo["title"]
                        retries_w_scs = self.videoinfo["retries_of_rerecording_had_scs"]
                        retries_total = self.videoinfo["retries_of_rerecording"]
                        if newmetadata is not None:
                            self.videoinfo = newmetadata
                            self.videoinfo["endedLogAt"] = self.ended_at.timestamp()
                            self.videoinfo["retries_of_rerecording_had_scs"] = retries_w_scs
                            self.videoinfo["retries_of_rerecording"] = retries_total
                            self.videoinfo["createdDateTime"] = createdDateTime
                            self.videoinfo["caught_while"] = caught_while
                            if self.videoinfo["title"] != old_title:
                                self.videoinfo["old_title"] = old_title
                        else:
                            print("couldn't retrieve new metadata for",self.videoid,old_title)
                    else:
                        caughtlive = False
                    if self.msg_counter > 0 and not self.chat_err:
                        had_scs += 1
                        self.videoinfo["retries_of_rerecording_had_scs"] = had_scs
                        self.total_counted_msgs = 0
                    self.videoinfo["startedLogAt"] = self.started_at.timestamp()
                    self.videoinfo["retries_of_rerecording"] = repeats
                    await self.update_psql_metadata()
                    self.metadata_list.append(self.videoinfo)
                else:
                    await self.log_output(self.videoinfo["title"]+" is not a broadcast recording or premiere")
                    return
            repeats += 1
            if repeats >= 1 and not self.cancelled and had_scs < 2 and caughtlive:
                await self.log_output("Waiting "+str(self.minutes_wait)+" minutes before re-recording sc-logs")
                await asyncio.sleep(self.minutes_wait*60)
        self.running = False
        await self.log_output("writing to files")
        proper_sc_list = []
        unique_currency_donors={}
        for msg in self.sc_msgs:
            msg_loaded = json.loads(msg)
            donations = self.donors[msg_loaded["userid"]]["donations"].setdefault(msg_loaded["currency"],[0,0])
            self.donors[msg_loaded["userid"]]["donations"][msg_loaded["currency"]][0] = donations[0] + 1 #amount of donations
            self.donors[msg_loaded["userid"]]["donations"][msg_loaded["currency"]][1] = donations[1] + msg_loaded["value"] #total amount of money donated
            proper_sc_list.append(msg_loaded)
            self.unique_donors.setdefault(msg_loaded["currency"], set())
            self.unique_donors[msg_loaded["currency"]].add(msg_loaded["userid"])
        for currency in self.unique_donors.keys():
            unique_currency_donors[currency] = len(self.unique_donors[currency])
        self.stats.append(await self.loop.run_in_executor(self.t_pool, recount_money, proper_sc_list))
        f = open(self.sc_file, "w")
        f_stats = open(self.stats_file, "w")
        f.write(json.dumps(proper_sc_list))
        print(len(proper_sc_list), "unique messages written")
        f.close()
        f_stats.write(json.dumps([self.metadata_list[0], self.stats[-1], unique_currency_donors]))
        f_stats.close()
        f_donors = open(self.donor_file,"w")
        f_donors.write(json.dumps(self.donors))
        f_donors.close()
        await self.conn.close()
        if self.cancelled:
            os.rename(f.name, f.name+".cancelled")
            os.rename(f_stats.name, f_stats.name + ".cancelled")
            os.rename(f_donors.name, f_donors.name + ".cancelled")
        if not self.chat_err and self.gen_wc and len(self.sc_msgs) > 0 and repeats >= 1 and not self.cancelled:
            await self.loop.run_in_executor(self.t_pool, self.generate_wordcloud, proper_sc_list)

    async def display(self,data,amount):
        if len(data.items) > 0:
            start = datetime.now()
            chatters = []
            channels = []
            messages = []
            for c in data.items: #data.items contains superchat messages - save them in list while also saving the calculated
                if c.type == "placeholder":
                    self.placeholders += 1
                #sums in a list
                if c.type == "superChat" or c.type == "superSticker":
                    if c.currency in self.clean_currency.keys():
                        c.currency = self.clean_currency[c.currency]
                    sc_datetime = datetime.fromtimestamp(c.timestamp/1000.0,timezone.utc)
                    sc_weekday = sc_datetime.weekday()
                    sc_hour = sc_datetime.hour
                    sc_minute = sc_datetime.minute
                    sc_user = c.author.name
                    sc_userid = c.author.channelId
                    chatters.append((sc_userid,sc_user,sc_datetime))
                    channels.append((sc_userid, sc_user, False))
                    if sc_userid not in self.donors.keys():
                        self.donors[sc_userid] = {"names":[sc_user],
                                                 "donations": {}}
                    else:
                        if sc_user not in self.donors[sc_userid]["names"]:
                            self.donors[sc_userid]["names"].append(sc_user)
                    sc_message = c.message
                    sc_color = c.bgColor
                    sc_currency = c.currency.replace(u'\xa0', '')
                    sc_info = {"time":c.timestamp,"currency":sc_currency,"value":c.amountValue,"weekday":sc_weekday,
                               "hour":sc_hour,"minute":sc_minute, "userid":sc_userid, "message":sc_message,
                               "color":sc_color, "debugtime":sc_datetime.isoformat()}
                    messages.append((self.videoid,sc_userid,sc_message,sc_datetime,sc_currency,Decimal(c.amountValue),sc_color))
                    self.stats.append(amount)
                    self.sc_msgs.add(json.dumps(sc_info))
                    self.total_counted_msgs += 1
            self.msg_counter = amount["amount_sc"]
            async with self.conn.transaction():
                await self.insert_channels.executemany(channels)
                await self.channel_name_history.executemany(chatters)
                await self.insert_messages.executemany(messages)
            end = datetime.now()
            await self.log_output(end.isoformat() + ": "+
                self.videoinfo["channel"] + " " + self.videoinfo["title"] + " " + data.items[-1].elapsedTime + " " +
                str(self.msg_counter) + "/"+str(self.total_counted_msgs) + " took "+ str((end-start).total_seconds()*1000)+" ms, placeholders: " + str(self.placeholders))

    def generate_wordcloud(self,log):
        wordcloudmake = superchat_wordcloud(log, logname=self.videoid)
        wordcloudmake.generate()

    async def log_output(self,logmsg):
        await self.loop.run_in_executor(self.t_pool,print,logmsg)

if __name__ =='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('yt_vid_id', metavar='N', type=str,
                        help='The YouTube livestream/video ID', default='')
    parser.add_argument('--suffix', action='store', type=str, help='suffix for savefiles', default="")
    parser.add_argument('-wc','--wordcloud', action='store_true', help='set this flag to generate wordcloud after superchats have been recorded')
    args = parser.parse_args()
    yt_api_key = "I am stupid. The old API key is now invalid."
    keyfile = open("yt_api_key.txt", "r")
    yt_api_key = keyfile.read()
    keyfile.close()
    loop = asyncio.get_event_loop()
    analysis = SuperchatArchiver(args.yt_vid_id,yt_api_key,args.wordcloud,loop,args.suffix)
    try:
        loop.run_until_complete(analysis.main())
    except asyncio.CancelledError:
        pass
