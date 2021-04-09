

'''Display the total result up to that point 
   at regular intervals.
   video_id can be both live and archived.'''
import asyncio, pytz
import argparse, time, os
import json, isodate
from datetime import datetime, timezone, timedelta
import pathlib
from concurrent.futures import CancelledError
from pytchat import (LiveChatAsync, 
     SuperchatCalculator, SuperChatLogProcessor)
from youtube_api import YouTubeDataAPI

class SuperchatArchiver:
    def __init__(self,vid_id, api_key):
        self.api_points_used = 1.0
        self.api = YouTubeDataAPI(api_key) #uses 1p to check key
        self.videoid = vid_id
        self.channel_id = ""
        self.metadata = {}
        #self.videolist = {}
        self.videoinfo = {}
        self.stats = []
        self.dict_list = []
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
                          "₹": "INR"}

        self.metadata = self.get_video_info(self.videoid)
        self.running = True
        if self.metadata is not None:
            #self.videolist[self.videoid] = self.metadata
            self.videoinfo = self.metadata
            self.channel_id = self.metadata["channelId"]
        else:
            exit(-1)

        pathlib.Path('./' + self.channel_id + '/sc_logs').mkdir(parents=True, exist_ok=True)
        pathlib.Path('./' + self.channel_id + '/vid_stats').mkdir(parents=True, exist_ok=True)

    def get_video_info(self,video_ID:str):
        try:
            response = self.api.get_video_metadata(video_id=video_ID, parser=None,
                                                   part=["liveStreamingDetails", "contentDetails", "snippet"])
            self.channel_id = response["snippet"]["channelId"]
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
            self.api_points_used += 1.0
            return api_metadata

        except Exception as e:
            print(self.videoid)
            #print(response)
            print(e)
            return None

    async def main(self):
        self.chat_err = True
        retries = 0
        while self.chat_err:
            if "liveStreamingDetails" in self.videoinfo.keys() or self.videoinfo["live"] != "none":
                self.stats.clear()
                #self.dict_list.clear()
                self.chat_err = False
                test_file = pathlib.Path(self.channel_id+"/sc_logs/"+self.videoid + ".txt")
                if test_file.is_file():
                    if test_file.stat().st_size > 2:
                        print(self.videoinfo["channel"]+" - " + self.videoinfo["title"]+" already analyzed, skipping. Existing file size: "+str(test_file.stat().st_size)+" bytes")
                        continue
                f = open(self.channel_id+"/sc_logs/"+self.videoid + ".txt", "w")
                f_stats = open(self.channel_id+"/vid_stats/"+self.videoid + "_stats.txt", "w")
                print("Started Analysis at: "+datetime.now(tz=pytz.timezone('Europe/Berlin')).isoformat())
                print("Analyzing Video " + datetime.fromtimestamp(self.videoinfo["publishDateTime"],timezone.utc).isoformat() + " " +self.videoinfo["channel"]+" - " + self.videoinfo["title"] + " ["+self.videoid+"]")
                chat = LiveChatAsync(self.videoid, callback = self.display, processor = (SuperChatLogProcessor(), SuperchatCalculator()))
                while chat.is_alive():
                    await asyncio.sleep(3)
                newmetadata = self.get_video_info(self.videoid)
                if newmetadata["live"] in ["upcoming","live"]:
                    print(datetime.now(tz=pytz.timezone('Europe/Berlin')).isoformat()+": Error! Chat monitor ended prematurely!")
                    print(chat.is_alive())
                    self.chat_err = True
                if self.videoinfo["caught_while"] in ["upcoming","live"]:
                    createdDateTime = self.videoinfo["publishDateTime"]
                    caught_while = self.videoinfo["caught_while"]
                    #newmetadata = get_video_info(videoid)
                    if newmetadata is not None:
                        self.videoinfo = newmetadata
                        self.videoinfo["createdDateTime"] = createdDateTime
                        self.videoinfo["caught_while"] = caught_while
                    else:
                        exit(-1)
                print("writing to files")
                f.write(json.dumps(self.dict_list))
                f.close()
                f_stats.write(json.dumps([self.videoinfo,self.stats[-1:]]))
                f_stats.close()
                if self.chat_err:
                    os.rename(f.name, f.name+".err"+str(retries))
                    os.rename(f_stats.name, f_stats.name + ".err"+str(retries))
                    retries +=1
            else:
                print(self.videoinfo["title"]+" is not a broadcast recording or premiere")
        self.running = False

    async def display(self,data,amount):
        if len(data.items) > 0:
            print(self.videoinfo["channel"],self.videoinfo["title"],data.items[-1].elapsedTime, amount["amount_sc"])#,amount)
            for c in data.items:
                if c.type == "superChat" or c.type == "superSticker":
                    if c.currency in self.clean_currency.keys():
                        c.currency = self.clean_currency[c.currency]
                    sc_datetime = datetime.fromtimestamp(c.timestamp/1000.0,timezone.utc)
                    sc_weekday = sc_datetime.weekday()
                    sc_hour = sc_datetime.hour
                    sc_minute = sc_datetime.minute
                    sc_user = c.author.name
                    sc_userid = c.author.channelId
                    sc_message = c.message
                    sc_color = c.bgColor
                    sc_info = {"time":c.timestamp,"currency":c.currency,"value":c.amountValue,"weekday":sc_weekday,
                               "hour":sc_hour,"minute":sc_minute,"user":sc_user, "userid":sc_userid, "message":sc_message,
                               "color":sc_color, "debugtime":sc_datetime.isoformat()}
                    #if self.chat_err:
                     #   for currency in self.stats[-1].keys():
                      #      if currency in amount.keys():
                       #         amount[currency] += self.stats[-1][currency]
                        #    else:
                         #       amount[currency] = self.stats[-1][currency]
                    self.stats.append(amount)
                    self.dict_list.append(sc_info)

if __name__ =='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('yt_vid_id', metavar='N', type=str,
                        help='The YouTube livestream/video ID', default='')
    args = parser.parse_args()
    yt_api_key = "I am stupid. The old API key is now invalid."
    keyfile = open("yt_api_key.txt", "r")
    yt_api_key = keyfile.read()
    keyfile.close()
    analysis = SuperchatArchiver(args.yt_vid_id,yt_api_key)
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(analysis.main())
    except asyncio.CancelledError:
        pass
