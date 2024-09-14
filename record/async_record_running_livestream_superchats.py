#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio, pytz, argparse, os, json, isodate, pathlib, concurrent.futures, asyncpg, copy, logging, httpx
from datetime import datetime, timezone
from pytchat import (LiveChatAsync, SuperchatCalculator, SuperChatLogProcessor, config, exceptions)
from youtube_api import YouTubeDataAPI
from merge_SC_logs_v2 import recount_money
from decimal import Decimal
from database.psql_db import PostgresDB

class SuperchatArchiver:
    def __init__(self,vid_id, api_key, loop = None, file_suffix = ".standalone.txt", minutes_wait = 30, retry_attempts = 72, min_successful_attempts = 2, logger = None, t_pool = concurrent.futures.ThreadPoolExecutor(max_workers=100)):
        self.total_counted_msgs = 0
        self.total_new_members = 0
        self.max_retry_attempts = retry_attempts
        self.min_successful_attempts = min_successful_attempts
        self.file_suffix = file_suffix
        self.minutes_wait = minutes_wait
        self.started_at = None
        self.ended_at = None
        self.cancelled = False
        self.loop = loop
        self.t_pool = t_pool
        self.timezone = pytz.timezone('Europe/Berlin')
        self.api_points_log = [(1.0,datetime.now(tz=self.timezone))]
        self.api = YouTubeDataAPI(api_key) #uses 1p to check key
        self.videoid = vid_id
        self.channel_id = ""
        self.metadata = {}
        self.videoinfo = {}
        self.donors = {}
        self.stats = []
        self.sc_msgs = dict()
        self.sc_logs_list = []
        self.metadata_list = []
        self.waiting = False
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
        self.api_points_log.append((1.0,datetime.now(tz=self.timezone)))
        self.total_member_msgs = 0
        self.running = True
        self.running_chat = None
        if self.metadata is not None:
            self.videoinfo = self.metadata
            self.videoinfo["retries_of_rerecording_had_scs"] = 0
            self.videoinfo["retries_of_rerecording"] = 0
            self.videoinfo["membership"] = False
            self.videoPostedAt = copy.deepcopy(self.videoinfo["publishDateTime"])
            self.channel_id = self.metadata["channel_id"]
        else:
            self.videoPostedAt = 0
            self.channel_id = "privatted-deleted-memebershipped"
        self.skeleton_dict = {"channel": None,
                              "channel_id": None,
                              "video_id": None,
                              "title": None,
                              "membership": False,
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
        path_prefix = f"txtarchive/{self.channel_id}"
        self.sc_file = f"{path_prefix}/sc_logs/{self.videoid}.txt{self.file_suffix}"
        self.donor_file = f"{path_prefix}/vid_stats/donors/{self.videoid}.txt{self.file_suffix}"
        self.stats_file = f"{path_prefix}/vid_stats/{self.videoid}_stats.txt{self.file_suffix}"
        pathlib.Path(self.sc_file).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(self.donor_file).parent.mkdir(parents=True, exist_ok=True)
        self.placeholders = 0
        if logger:
            self.logger = logger
        else:
            self.logger = logging.getLogger(__name__)
            self.logger.setLevel(logging.DEBUG)
            fh = logging.FileHandler(f'./txtarchive/{self.channel_id}/{self.videoid}.applog')
            fh.setLevel(logging.DEBUG)
            ch = logging.StreamHandler()
            ch.setLevel(logging.INFO)
            dbg_formatter = config.mylogger.MyFormatter()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            fh.setFormatter(dbg_formatter)
            ch.setFormatter(formatter)
            self.logger.addHandler(fh)
            self.logger.addHandler(ch)
        with open("postgres-config.json") as pgsql_config_file:
            self.pgsql_creds = json.load(pgsql_config_file)
        self.db = PostgresDB(username = self.pgsql_creds["username"], password = self.pgsql_creds["password"],
                             host = self.pgsql_creds["host"], database = self.pgsql_creds["database"])

    def __str__(self):
        return f'[{self.videoid}] {self.videoinfo.get("channel", "")} - {self.videoinfo.get("title","")} - Running: {self.running} Live: {self.videoinfo.get("live", "")}'
    
    def __repr__(self):
        return f'[{self.videoid}] {self.videoinfo.get("channel", "")} - {self.videoinfo.get("title","")} - Running: {self.running} Live: {self.videoinfo.get("live", "")}'

    def get_video_info(self,video_ID: str):
        response = None
        try:
            response = self.api.get_video_metadata(video_id=video_ID, parser=None,
                                                   part=["liveStreamingDetails", "contentDetails", "snippet"])
            api_metadata = {"channel": response["snippet"]["channelTitle"],
                            "channel_id": response["snippet"]["channelId"],
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
                            f'{response["liveStreamingDetails"][d]} +0000', "%Y-%m-%dT%H:%M:%SZ %z").timestamp()
            return api_metadata

        except Exception as e:
            print(self.videoid)
            print(e)
            print(response)
            return None

    async def async_get_video_info(self, video_ID: str):
        self.api_points_log.append((1.0,datetime.now(tz=self.timezone)))
        api_metadata = await self.loop.run_in_executor(self.t_pool,self.get_video_info,video_ID)
        return api_metadata

    def cancel(self):
        self.cancelled = True
        if self.running_chat:
            self.running_chat.terminate()

    async def already_done(self):
        successful_sc_recordings, repeats = await self.db.get_retries(self.videoid)
        test_file = pathlib.Path(self.sc_file)
        file_has_content = False
        if test_file.is_file():
            file_has_content = test_file.stat().st_size > 2
        if successful_sc_recordings >= self.min_successful_attempts and file_has_content:
            return file_has_content, test_file.stat().st_size, successful_sc_recordings, repeats
        else:
            return False, 0, successful_sc_recordings, repeats

    async def main(self):
        if not self.loop:
            self.loop = asyncio.get_running_loop()
        await self.log_output(self.videoinfo,10)
        #fetch old video metadata
        self.db_task = asyncio.create_task(self.db.flush_on_event())
        old_meta = await self.db.get_video_metadata(self.videoid)
        if old_meta:
            old_time_meta = {"scheduledStartTime": old_meta["scheduledstarttime"].timestamp() if old_meta["scheduledstarttime"] else 0,
                             "actualStartTime": old_meta["actualstarttime"].timestamp() if old_meta["actualstarttime"] else 0,
                             "actualEndTime": old_meta["actualendtime"].timestamp() if old_meta["actualendtime"] else 0}
            if self.videoinfo:
                for time in old_time_meta.keys():
                    if "liveStreamingDetails" in self.videoinfo.keys():
                        if time in self.videoinfo["liveStreamingDetails"].keys():
                            if not old_time_meta[time] and self.videoinfo["liveStreamingDetails"][time]:
                                old_time_meta[time] = self.videoinfo["liveStreamingDetails"][time]
            time_meta_keys = list(old_time_meta.keys())
            for timekey in time_meta_keys:
                if not old_time_meta[timekey]:
                    old_time_meta.pop(timekey)
            old_meta["liveStreamingDetails"] = old_time_meta
            if not self.videoinfo:
                self.videoinfo = copy.deepcopy(self.skeleton_dict)
            await self.log_output(self.videoinfo,10)
            if self.videoinfo["title"] != old_meta["title"] and self.videoinfo["title"]:
                old_meta["old_title"] = old_meta["title"]
                old_meta["title"] = self.videoinfo["title"]
            old_meta_keys_l = [k.lower() for k in old_meta.keys()]
            old_meta_keys_n = [k for k in old_meta.keys()]
            old_meta_keys = dict(zip(old_meta_keys_l, old_meta_keys_n))
            #await self.log_output(old_meta_keys,10)
            for info in self.skeleton_dict.keys():
                if info.lower() in old_meta_keys_l:
                    if type(old_meta[old_meta_keys[info.lower()]]) is datetime:
                        self.videoinfo[info] = old_meta[old_meta_keys[info.lower()]].timestamp()
                    elif old_meta[old_meta_keys[info.lower()]]:
                        self.videoinfo[info] = old_meta[old_meta_keys[info.lower()]]
                    elif old_meta[old_meta_keys[info.lower()]] is None and "time" in info.lower():
                        if info in self.videoinfo.keys():
                            await self.log_output((info,"key found", self.videoinfo[info],self.videoinfo.keys()))
                            self.videoinfo[info] = self.videoinfo[info] if self.videoinfo[info] else 0
                        else:
                            await self.log_output((info,"key not found",self.videoinfo[info],self.videoinfo.keys()))
                            self.videoinfo[info] = 0
                    else:
                        await self.log_output(("else case",old_meta[old_meta_keys[info.lower()]],info.lower()),10)
            self.channel_id = old_meta["channel_id"]
            self.videoinfo["channel"] = old_meta["name"]
            self.videoinfo["channel_id"] = self.channel_id
            self.videoinfo["video_id"] = self.videoid
            self.videoPostedAt = self.videoinfo['publishDateTime']
            self.metadata_list.append(self.videoinfo)
            self.ended_at = old_meta["endedlogat"] if old_meta["endedlogat"] else None
            self.videoinfo["endedLogAt"] = self.ended_at.timestamp() if self.ended_at else None
            if self.metadata:
                self.videoinfo["live"] = self.metadata["live"]
        await self.log_output(self.videoinfo)
        if not self.videoinfo:
            return
        await self.db.insert_channel_metadata(self.channel_id, self.videoinfo["channel"], True)
        dtnow = datetime.now(tz=self.timezone)
        await self.db.insert_chan_name_hist(self.channel_id, self.videoinfo["channel"], dtnow, dtnow)
        self.db.trigger()
        self.chat_err = True
        log_exist_test, filesize, db_retries_had_scs, repeats = await self.already_done()
        self.videoinfo["retries_of_rerecording_had_scs"] = db_retries_had_scs
        self.videoinfo["retries_of_rerecording"] = repeats
        islive = True
        already_recorded = False
        if log_exist_test:
            await self.log_output("{0} - {1} already analyzed, skipping. Existing file size: {2} bytes".format(
                self.videoinfo["channel"],self.videoinfo["title"],filesize))
            already_recorded = True
        had_scs = db_retries_had_scs if db_retries_had_scs else 0
        self.msg_counter = 0
        if had_scs >= self.min_successful_attempts:
            await self.log_output("{0} - {1} already fully analyzed according to database, skipping".format(
                self.videoinfo["channel"],self.videoinfo["title"]))
            already_recorded = True
        while (repeats < self.max_retry_attempts and had_scs < self.min_successful_attempts and not self.cancelled and islive and not already_recorded):
            self.msg_counter = 0
            self.total_member_msgs = 0
            self.total_new_members = 0
            self.chat_err = True
            if self.metadata:
                islive = self.metadata["live"] in ["upcoming","live"]
            while self.chat_err and not self.cancelled:
                if "liveStreamingDetails" in self.videoinfo.keys() or self.videoinfo["live"] != "none" or repeats >= 1:
                    self.stats.clear()
                    self.chat_err = False
                    self.started_at = datetime.now(tz=self.timezone)
                    publishtime = datetime.fromtimestamp(self.videoPostedAt,timezone.utc)
                    #insert video metadata
                    await self.db.insert_video_metadata(self.videoid, self.videoinfo["channel_id"],
                                                  self.videoinfo["title"], self.started_at, publishtime)
                    self.db.trigger()
                    paramdict = {k: v for k, v in self.videoinfo.items() if k != "liveStreamingDetails"}
                    await self.db.update_metadata(**paramdict, **self.videoinfo["liveStreamingDetails"])
                    await self.log_output(f"Starting Analysis #{repeats + 1} at: {self.started_at.isoformat()}")
                    await self.log_output(f'of video {publishtime.isoformat()} {self.videoinfo["channel"]} - {self.videoinfo["title"]} [{self.videoid}]')
                    if repeats >= 1:
                        await self.log_output("Recording the YouTube-archived chat after livestream finished")
                    self.httpclient = httpx.AsyncClient(http2=True)
                    self.running_chat = LiveChatAsync(self.videoid, callback = self.display, processor = (SuperChatLogProcessor(), SuperchatCalculator()),logger=self.logger, client = self.httpclient, exception_handler = self.exception_handling)
                    await self.log_output("starting...")
                    while self.running_chat.is_alive() and not self.cancelled:
                        await asyncio.sleep(3)
                    try:
                        await self.log_output(str(self.running_chat.exception),20)
                        await self.log_output(str(type(self.running_chat.exception)),20)
                        self.running_chat.raise_for_status()
                    except exceptions.NoContents:
                        if self.running_chat.member_stream:
                            self.cancel()
                            await self.log_output("a member stream detected",30)
                    except exceptions.InvalidVideoIdException:
                        self.cancel() #Video ID invalid: Private or Membership vid or deleted. Treat as cancelled
                    except exceptions.ChatParseException: #ChatParseException: No chat found
                        await self.log_output("no chat detected/parse error",30)
                    except Exception as e:
                        #In case of error, cancel always if member stream detected
                        if self.running_chat.member_stream:
                            self.cancel()
                            await self.log_output("member stream detected",30)
                        await self.log_output(str(type(e)),30)
                        await self.log_output(str(e),30)
                    self.videoinfo["membership"] = self.running_chat.member_stream
                    if repeats == 0 and not self.chat_err and not self.cancelled and not self.ended_at:
                        self.ended_at = datetime.now(tz=self.timezone)
                        self.videoinfo["endedLogAt"] = self.ended_at.timestamp()
                    await self.httpclient.aclose()
                    newmetadata = await self.async_get_video_info(self.videoid) #when livestream chat parsing ends, get some more metadata
                    if newmetadata is not None:
                        if newmetadata["live"] in ["upcoming","live"] and not self.cancelled: #in case the livestream has not ended yet!
                            await self.log_output(("Error! Chat monitor ended prematurely!",self.running_chat.is_alive()),30)
                            self.chat_err = True
                    else:
                        islive = False
                    if self.videoinfo["caught_while"] in ["upcoming","live"]:
                        #use newer metadata while rescuing certain fields from the old metadata
                        createdDateTime = self.videoPostedAt
                        caught_while = self.videoinfo["caught_while"]
                        old_title = self.videoinfo["title"]
                        retries_w_scs = self.videoinfo["retries_of_rerecording_had_scs"]
                        retries_total = self.videoinfo["retries_of_rerecording"]
                        is_member_stream = self.videoinfo["membership"]
                        if newmetadata is not None:
                            self.videoinfo = newmetadata
                            self.videoinfo["endedLogAt"] = self.ended_at.timestamp() if self.ended_at else None
                            self.videoinfo["retries_of_rerecording_had_scs"] = retries_w_scs
                            self.videoinfo["retries_of_rerecording"] = retries_total
                            self.videoinfo["createdDateTime"] = createdDateTime
                            self.videoinfo["caught_while"] = caught_while
                            self.videoinfo["membership"] = is_member_stream
                            if self.videoinfo["title"] != old_title:
                                self.videoinfo["old_title"] = old_title
                        else:
                            self.videoinfo["live"] = "none"
                            await self.log_output(("couldn't retrieve new metadata for",self.videoid,old_title),30)
                    else:
                        islive = False
                    if (self.msg_counter+self.total_member_msgs) > 0 and not self.chat_err and not self.cancelled:
                        had_scs += 1
                        self.videoinfo["retries_of_rerecording_had_scs"] = had_scs
                        self.total_counted_msgs = 0
                    self.videoinfo["startedLogAt"] = self.started_at.timestamp()
                    self.videoinfo["retries_of_rerecording"] = repeats
                    paramdict = {k: v for k, v in self.videoinfo.items() if k != "liveStreamingDetails"}
                    await self.db.update_metadata(**paramdict, **self.videoinfo["liveStreamingDetails"])
                    self.metadata_list.append(self.videoinfo)
                else:
                    await self.log_output("{0} is not a broadcast recording or premiere".format(self.videoinfo["title"]))
                    return
            repeats += 1
            await self.log_output((repeats,self.cancelled,had_scs,self.videoinfo["live"]))
            if repeats >= 1 and not self.cancelled and had_scs < 2 and islive:
                await self.log_output(f"Waiting {self.minutes_wait} minutes before re-recording sc-logs")
                await asyncio.sleep(self.minutes_wait*60)
        self.running = False
        self.db.running = self.running
        self.db_task.cancel()
        if not already_recorded:
            await self.log_output("writing to files")
            proper_sc_list = []
            unique_currency_donors={}
            count_scs = 0
            for c_id, msg in self.sc_msgs.items():
                msg["id"] = c_id
                if msg["type"] not in ["newSponsor", "sponsorMessage", "giftRedemption"]:
                    count_scs += 1
                    self.donors.setdefault(msg["userid"],{})
                    donations = self.donors[msg["userid"]]["donations"].setdefault(msg["currency"],[0,0])
                    self.donors[msg["userid"]]["donations"][msg["currency"]][0] = donations[0] + 1 #amount of donations
                    self.donors[msg["userid"]]["donations"][msg["currency"]][1] = donations[1] + msg["value"] #total amount of money donated
                    self.unique_donors.setdefault(msg["currency"], set())
                    self.unique_donors[msg["currency"]].add(msg["userid"])
                proper_sc_list.append(msg)
            for currency in self.unique_donors.keys():
                unique_currency_donors[currency] = len(self.unique_donors[currency])
            f = open(self.sc_file, "w")
            f_stats = open(self.stats_file, "w")
            f.write(json.dumps(proper_sc_list))
            await self.log_output(f"{len(proper_sc_list)} unique messages written, {count_scs} are superchats")
            f.close()
            self.stats.append(await self.loop.run_in_executor(self.t_pool, recount_money, proper_sc_list))
            f_stats.write(json.dumps([self.metadata_list[-1], self.stats[-1], unique_currency_donors]))
            f_stats.close()
            f_donors = open(self.donor_file,"w")
            f_donors.write(json.dumps(self.donors))
            f_donors.close()
            if self.cancelled:
                os.rename(f.name, f.name+".cancelled")
                os.rename(f_stats.name, f_stats.name + ".cancelled")
                os.rename(f_donors.name, f_donors.name + ".cancelled")

    async def display(self,data,amount):
        if len(data.items) > 0:
            start = datetime.now(timezone.utc)
            for c in data.items: #data.items contains superchat messages - save them in list while also saving the calculated
                if c.type == "placeholder":
                    self.placeholders += 1
                if c.type in ["newSponsor", "giftRedemption"]:
                    sc_datetime = datetime.fromtimestamp(c.timestamp/1000.0,timezone.utc)
                    sc_info = {"type": c.type, "time":c.timestamp,
                               "userid":c.author.channelId, "member_level": c.member_level, "debugtime":sc_datetime.isoformat()}
                    self.total_new_members += 1
                    self.sc_msgs.setdefault(c.id, sc_info)
                #sums in a list
                if c.type in ["superChat","superSticker","sponsorMessage","giftPurchase"]:
                    if c.currency in self.clean_currency.keys():
                        c.currency = self.clean_currency[c.currency]
                    sc_datetime = datetime.fromtimestamp(c.timestamp/1000.0,timezone.utc)
                    name_used_datetime = start if self.videoinfo["live"] == "none" else sc_datetime
                    sc_weekday = sc_datetime.weekday()
                    sc_hour = sc_datetime.hour
                    sc_minute = sc_datetime.minute
                    sc_user = c.author.name
                    sc_userid = c.author.channelId
                    chat_id = c.id
                    await self.db.insert_chan_name_hist(sc_userid,sc_user,sc_datetime,name_used_datetime)
                    await self.db.insert_channel_metadata(sc_userid, sc_user, False)
                    if sc_userid not in self.donors.keys():
                        self.donors[sc_userid] = {"names":[sc_user],
                                                 "donations": {}}
                    else:
                        if sc_user not in self.donors[sc_userid]["names"]:
                            self.donors[sc_userid]["names"].append(sc_user)
                    sc_message = c.message
                    sc_color = c.bgColor
                    sc_currency = c.currency.replace(u'\xa0', '')
                    sc_info = {"type": c.type, "time":c.timestamp,"currency":sc_currency,"value":c.amountValue,"weekday":sc_weekday,
                               "hour":sc_hour,"minute":sc_minute, "userid":sc_userid, "message":sc_message,
                               "color":sc_color, "debugtime":sc_datetime.isoformat()}
                    if c.type == "sponsorMessage":
                        self.total_member_msgs += 1
                        sc_info["member_level"] = c.member_level
                    elif c.type != "giftPurchase":
                        self.total_counted_msgs += 1
                    await self.db.insert_message(self.videoid,chat_id,sc_userid,sc_message,sc_datetime,sc_currency,Decimal(c.amountValue),sc_color)
                    self.stats.append(amount)
                    self.sc_msgs.setdefault(chat_id, sc_info)
                    if sc_currency == '':
                        print("Empty currency!",sc_currency, c.type, sc_info)
                        if c.type == "superChat":
                            print("raw currency",c.amountString)
            self.msg_counter = amount["amount_sc"]
            self.db.trigger()
            end = datetime.now(timezone.utc)
            await self.log_output(
                f'{self.videoinfo["channel"]} {self.videoinfo["title"]} {data.items[-1].elapsedTime} '
                f"{self.msg_counter}/{self.total_counted_msgs} superchats, "
                f"{self.total_new_members} new members, "
                f"{self.total_member_msgs} member anniversary scs took {(end - start).total_seconds() * 1000} ms, "
                f"placeholders: {self.placeholders}")

    async def log_output(self,logmsg,level = 20):
        msg_string = ""
        msg_len = len(logmsg)
        if isinstance(logmsg, tuple):
            part_count = 0
            for msg_part in logmsg:
                part_count += 1
                msg_string += str(msg_part)
                if msg_len > part_count:
                    msg_string += " "
        elif isinstance(logmsg, str):
            msg_string = logmsg
        else:
            msg_string = str(logmsg)
        await self.loop.run_in_executor(self.t_pool,self.logger.log,level,msg_string)
        
    
    def exception_handling(self,loop,context):
        ex_time = datetime.now(timezone.utc)
        self.logger.log(40,f"[{self.videoid}] Exception caught")
        self.logger.log(40,context)

if __name__ =='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('yt_vid_id', metavar='N', type=str,
                        help='The YouTube livestream/video ID', default='')
    parser.add_argument('--suffix', action='store', type=str, help='suffix for savefiles', default="")
    args = parser.parse_args()
    yt_api_key = "I am stupid. The old API key is now invalid."
    keyfile = open("yt_api_key.txt", "r")
    yt_api_key = keyfile.read()
    keyfile.close()
    loop = asyncio.get_event_loop()
    analysis = SuperchatArchiver(args.yt_vid_id,yt_api_key,loop,args.suffix)
    try:
        loop.run_until_complete(analysis.main())
    except asyncio.CancelledError:
        pass
