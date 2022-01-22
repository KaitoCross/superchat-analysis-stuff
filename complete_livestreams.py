#!/usr/bin/env python3
from async_record_running_livestream_superchats import SuperchatArchiver
import argparse, time, os, asyncio, pytz, logging, signal, sys, asyncpg, json, concurrent.futures
from datetime import datetime, timezone, timedelta
import pytchat
import aiohttp
from aiohttp_requests import requests
import math
from youtube_api import YouTubeDataAPI
from pytchat import config

class redo_recorder:
    def __init__(self,chan_id,api_pts_used = 0.0, keyfilepath = "yt_api_key.txt"):
        self.running = True
        self.reset_used = False
        signal.signal(signal.SIGUSR1, self.signal_handler_1)
        signal.signal(signal.SIGUSR2, self.signal_handler_2)
        self.yt_api_key = "####"
        keyfile = open(keyfilepath, "r")
        self.yt_api_key = keyfile.read()
        keyfile.close()
        self.api_points_used = api_pts_used
        self.video_analysis = {}
        #self.chan_ids = chan_list
        self.running_streams = []
        self.analyzed_streams = []
        self.api_points = 10000.0 #available API points
        self.desired_leftover_points = 100.0 #for safety measure since the SuperchatArchiver objects will use some API points
        self.chan_id = chan_id
        self.videolist = []
        self.yapi = YouTubeDataAPI(self.yt_api_key)
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        fh = logging.FileHandler(keyfilepath+"record_completer.debuglog")
        fh.setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        dbg_formatter = config.mylogger.MyFormatter()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(dbg_formatter)
        ch.setFormatter(formatter)
        self.logger.addHandler(fh)
        self.logger.addHandler(ch)
        self.thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=128)

    async def main(self):
        cutoff_date = datetime(2020, 6, 1, 0, 0, 0, 0, tzinfo=timezone.utc)
        pgsql_config_file = open("postgres-config.json")
        pgsql_creds = json.load(pgsql_config_file)
        self.conn = await asyncpg.connect(user = pgsql_creds["username"], password = pgsql_creds["password"], host = pgsql_creds["host"], database = pgsql_creds["database"])
        query = "select video_id from video where retries_of_rerecording_had_scs = 2 and caught_while <> 'none' and scheduledstarttime < $1 and channel_id = $2 order by scheduledstarttime desc"
        old_streams = await self.conn.fetch(query,datetime.now(timezone.utc) - timedelta(hours = 12),self.chan_id)
        recorded_set = set(old_streams)
        channel_meta = self.yapi.get_channel_metadata(channel_id=self.chan_id,parser=None,list=["contentDetails"])
        self.api_points_used += 1
        upload_playlist = channel_meta["contentDetails"]["relatedPlaylists"]["uploads"]
        uploaded_videos = self.yapi.get_videos_from_playlist_id(upload_playlist,parser=None,list=["contentDetails"])
        uploaded_videos_sort = sorted(uploaded_videos,key = lambda d: d["snippet"]["publishedAt"], reverse = True)
        self.api_points_used += 1
        for videos in uploaded_videos_sort:
            publishedDate = datetime.strptime(videos["snippet"]["publishedAt"]+ " +0000", "%Y-%m-%dT%H:%M:%SZ %z")
            if publishedDate < cutoff_date:
                continue
            self.videolist.append(videos["snippet"]["resourceId"]["videoId"])
        channel_set = set(self.videolist)
        record_set = channel_set - recorded_set
        print(len(channel_set), len(record_set), record_set)
        for entry in record_set:
            self.video_analysis.setdefault(entry,None)
            self.running_streams.append(entry)
        print(self.video_analysis)
        for stream in list(self.video_analysis.keys()):
            self.video_analysis[stream] = SuperchatArchiver(stream,self.yt_api_key, file_suffix=".completer.txt",min_successful_attempts = 2,logger = self.logger, t_pool = self.thread_pool, minutes_wait = 0.5)
            try:
                await self.video_analysis[stream].main()
            except pytchat.exceptions.InvalidVideoIdException:
                print("aaa")
            self.analyzed_streams.append(stream)
        print("Streams analyzed:",len(self.analyzed_streams))

    async def total_api_points_used(self):
        points_used_by_analysis = 0.0
        for stream in self.video_analysis.keys():
            if self.video_analysis[stream] is not None:
                points_used_by_analysis += self.video_analysis[stream].api_points_used
        return points_used_by_analysis+self.api_points_used
    
    def syn_total_api_points_used(self):
        points_used_by_analysis = 0.0
        for stream in self.video_analysis.keys():
            if self.video_analysis[stream] is not None:
                points_used_by_analysis += self.video_analysis[stream].api_points_used
        pts_used = points_used_by_analysis+self.api_points_used
        return pts_used

    def signal_handler_1(self, sig, frame):
        for stream in self.video_analysis:
            if self.video_analysis[stream]:
                self.video_analysis[stream].cancel()
        #self.running = False
        print("cancelled logging")
        pts_used = syn_total_api_points_used()
        print("api points used:", pts_used)
        
    def signal_handler_2(self, sig, frame):
        worked_on = 0
        for stream in self.video_analysis:
            if self.video_analysis[stream]:
                print(self.video_analysis[stream])
                worked_on += 1
        not_touched = len(self.video_analysis) - worked_on
        print("worked on",worked_on,"items out of",len(self.video_analysis),"remaining:",not_touched)
        pts_used = syn_total_api_points_used()
        print("api points used:", pts_used)

if __name__ =='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--pts','-p', action='store', type=int, default=0, help='The amout of YouTube API points already used today')
    parser.add_argument('--keyfile','-k', action='store', type=str, default="", help='The file with the API key')
    parser.add_argument('channel_id', metavar='N', type=str, help='The YouTube channel ID')
    args = parser.parse_args()
    keyfilepath = str()
    if args.keyfile:
        keyfilepath = args.keyfile
    else:
        keyfilepath = "yt_api_key.txt"
    monitor = redo_recorder(args.channel_id,args.pts,keyfilepath)
    loop = asyncio.get_event_loop()
    #loop.set_debug(True)
    #logging.getLogger("asyncio").setLevel(logging.INFO)
    #logging.basicConfig(level=logging.INFO)
    try:
        loop.run_until_complete(monitor.main())
    except asyncio.CancelledError:
        pass
