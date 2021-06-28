import asyncio, pytz, argparse, time, os, functools, json, isodate, pathlib
from datetime import datetime, timezone, timedelta
from concurrent.futures import CancelledError
from pytchat import (LiveChatAsync, 
     SuperchatCalculator, SuperChatLogProcessor)
import concurrent.futures
from youtube_api import YouTubeDataAPI
from sc_wordcloud import superchat_wordcloud
from merge_SC_logs_v2 import recount_money

class SuperchatArchiver:
    def __init__(self,vid_id, api_key, gen_WC = False, loop = None, file_suffix = ".standalone.txt", minutes_wait = 30):
        self.file_suffix = file_suffix
        self.minutes_wait = minutes_wait
        self.started_at = datetime.now(tz=pytz.timezone('Europe/Berlin'))
        self.ended_at = None
        self.cancelled = False
        self.loop = loop
        self.t_pool = concurrent.futures.ThreadPoolExecutor(max_workers=100)
        self.api_points_used = 1.0
        self.api = YouTubeDataAPI(api_key) #uses 1p to check key
        self.videoid = vid_id
        self.channel_id = ""
        self.metadata = {}
        self.videoinfo = {"retries_of_rerecording_had_scs":0}
        self.donors = {}
        self.stats = []
        self.sc_msgs = set()
        self.sc_logs_list = []
        self.metadata_list = []
        self.gen_wc = gen_WC
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
        self.channel_id = self.metadata["channelId"]
        self.sc_file = self.channel_id + "/sc_logs/" + self.videoid + ".txt"+self.file_suffix
        self.donor_file = self.channel_id + "/vid_stats/donors/" + self.videoid + ".txt"+self.file_suffix
        self.stats_file = self.channel_id + "/vid_stats/" + self.videoid + "_stats.txt"+self.file_suffix
        self.running = True
        if self.metadata is not None:
            self.videoinfo = self.metadata
            self.channel_id = self.metadata["channelId"]
        else:
            exit(-1)
        print(self.metadata, self.channel_id, self.videoid, self.file_suffix)
        pathlib.Path('./' + self.channel_id + '/vid_stats/donors').mkdir(parents=True, exist_ok=True)
        pathlib.Path('./' + self.channel_id + '/sc_logs').mkdir(parents=True, exist_ok=True)

    def __str__(self):
        return self.videoinfo["channel"] + " - " + self.videoinfo["title"] + " - Running: "+str(self.running)

    def get_video_info(self,video_ID:str):
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
            return None

    async def async_get_video_info(self,video_ID:str):
        api_metadata = await self.loop.run_in_executor(self.t_pool,self.get_video_info,video_ID)
        self.api_points_used += 1.0
        self.channel_id = api_metadata["channelId"]
        return api_metadata

    def cancel(self):
        self.cancelled = True

    async def main(self):
        if not self.loop:
            self.loop = asyncio.get_running_loop()
        self.chat_err = True
        repeats = 0
        test_file = pathlib.Path(self.sc_file)
        if test_file.is_file():
            if test_file.stat().st_size > 2:
                await self.log_output(self.videoinfo["channel"] + " - " + self.videoinfo[
                    "title"] + " already analyzed, skipping. Existing file size: " + str(
                    test_file.stat().st_size) + " bytes")
                return
        had_scs = 0
        self.msg_counter = 0
        caughtlive = True
        while (repeats < 20 and had_scs < 2 and not self.cancelled and caughtlive):
            self.msg_counter = 0
            self.chat_err = True
            while self.chat_err and not self.cancelled:
                if "liveStreamingDetails" in self.videoinfo.keys() or self.videoinfo["live"] != "none" or repeats >= 1:
                    self.stats.clear()
                    self.chat_err = False
                    analysis_ts = datetime.now(tz=pytz.timezone('Europe/Berlin'))
                    await self.log_output("Started Analysis \#"+str(repeats+1)+" at: "+analysis_ts.isoformat())
                    await self.log_output("of video " + datetime.fromtimestamp(self.videoinfo["publishDateTime"],timezone.utc).isoformat() + " " +self.videoinfo["channel"]+" - " + self.videoinfo["title"] + " ["+self.videoid+"]")
                    if repeats >= 1:
                        await self.log_output("Recording the YouTube-archived chat after livestream finished")
                    chat = LiveChatAsync(self.videoid, callback = self.display, processor = (SuperChatLogProcessor(), SuperchatCalculator()))
                    while chat.is_alive() and not self.cancelled:
                        await asyncio.sleep(3)
                    newmetadata = await self.async_get_video_info(self.videoid) #when livestream chat parsing ends, get some more metadata
                    if newmetadata["live"] in ["upcoming","live"]: #in case the livestream has not ended yet!
                        await self.log_output(datetime.now(tz=pytz.timezone('Europe/Berlin')).isoformat()+": Error! Chat monitor ended prematurely!")
                        await self.log_output(chat.is_alive())
                        self.chat_err = True
                    if self.videoinfo["caught_while"] in ["upcoming","live"]:
                        #use newer metadata while rescuing certain fields from the old metadata
                        createdDateTime = self.videoinfo["publishDateTime"]
                        caught_while = self.videoinfo["caught_while"]
                        old_title = self.videoinfo["title"]
                        if newmetadata is not None:
                            self.videoinfo = newmetadata
                            self.videoinfo["createdDateTime"] = createdDateTime
                            self.videoinfo["caught_while"] = caught_while
                            if self.videoinfo["title"] != old_title:
                                self.videoinfo["old_title"] = old_title
                        else:
                            exit(-1)
                    else:
                        caughtlive = False
                    if self.msg_counter > 0 and not self.chat_err:
                        had_scs += 1
                        self.videoinfo["retries_of_rerecording_had_scs"] = had_scs
                    self.videoinfo["startedLogAt"] = analysis_ts.timestamp()
                    self.videoinfo["retries_of_rerecording"] = repeats
                    self.metadata_list.append(self.videoinfo)
                else:
                    await self.log_output(self.videoinfo["title"]+" is not a broadcast recording or premiere")
                    return
            repeats += 1
            if repeats >= 1 and not self.cancelled and had_scs < 2 and caughtlive:
                await self.log_output("Waiting "+str(self.minutes_wait)+" minutes before re-recording sc-logs")
                await asyncio.sleep(self.minutes_wait*60)
        self.running = False
        self.ended_at = datetime.now(tz=pytz.timezone('Europe/Berlin'))
        await self.log_output("writing to files")
        proper_sc_list = []
        for msg in self.sc_msgs:
            msg_loaded = json.loads(msg)
            donations = self.donors[msg_loaded["userid"]]["donations"].setdefault(msg_loaded["currency"],0)
            self.donors[msg_loaded["userid"]]["donations"][msg_loaded["currency"]] = donations + 1
            proper_sc_list.append(msg_loaded)
        self.stats.append(await self.loop.run_in_executor(self.t_pool, recount_money, proper_sc_list))
        f = open(self.sc_file, "w")
        f_stats = open(self.stats_file, "w")
        f.write(json.dumps(proper_sc_list))
        print(len(proper_sc_list), "unique messages written")
        f.close()
        f_stats.write(json.dumps([self.metadata_list[0], self.stats[-1]]))
        f_stats.close()
        f_donors = open(self.donor_file,"w")
        f_donors.write(json.dumps(self.donors))
        f_donors.close()
        if self.cancelled:
            os.rename(f.name, f.name+".cancelled")
            os.rename(f_stats.name, f_stats.name + ".cancelled")
            os.rename(f_donors.name, f_donors.name + ".cancelled")
        if not self.chat_err and self.gen_wc and len(self.sc_msgs) > 0 and repeats >= 1 and not self.cancelled:
            await self.loop.run_in_executor(self.t_pool, self.generate_wordcloud, proper_sc_list)

    async def display(self,data,amount):
        if len(data.items) > 0:
            for c in data.items: #data.items contains superchat messages - save them in list while also saving the calculated
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
                    self.stats.append(amount)
                    self.sc_msgs.add(json.dumps(sc_info))
            self.msg_counter = amount["amount_sc"]
            await self.log_output(
                self.videoinfo["channel"] + " " + self.videoinfo["title"] + " " + data.items[-1].elapsedTime + " " +
                str(self.msg_counter))

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
