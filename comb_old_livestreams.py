#!/usr/bin/env python3
from async_record_running_livestream_superchats import SuperchatArchiver
import argparse, time, os, asyncio, pytz, logging, signal, sys, asyncpg, json
from datetime import datetime, timezone, timedelta
import pytchat
import aiohttp
from aiohttp_requests import requests
import math

class redo_recorder:
    def __init__(self,api_pts_used = 0.0, keyfilepath = "yt_api_key.txt"):
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
        #self.max_watched_channels = len(self.chan_ids)
        #self.cost_per_request = 100.0
        #calculate how many times I can monitor all of the channels together using the Youtube search API (costs MANY API points)
        #self.requests_left = math.floor((self.api_points-self.api_points_used) / (self.max_watched_channels*self.cost_per_request))
        #Calculate how long I have to wait for the next search request - trying not to exceed the 24h API usage limits
        #self.sleep_dur = (60.0*60.0*24.0)/self.requests_left

    async def main(self):
        pgsql_config_file = open("postgres-config.json")
        pgsql_creds = json.load(pgsql_config_file)
        self.conn = await asyncpg.connect(user = pgsql_creds["username"], password = pgsql_creds["password"], host = pgsql_creds["host"], database = pgsql_creds["database"])
        query = "select video_id from video where (retries_of_rerecording_had_scs < 2 or retries_of_rerecording_had_scs is null) and caught_while <> 'none' and scheduledstarttime < $1 order by scheduledstarttime"
        old_streams = await self.conn.fetch(query,datetime.now(timezone.utc) - timedelta(hours = 12))
        for entry in old_streams:
            self.video_analysis.setdefault(entry[0],None)
            self.running_streams.append(entry[0])
        print(self.video_analysis)
        for stream in list(self.video_analysis.keys()):
            self.video_analysis[stream] = SuperchatArchiver(stream,self.yt_api_key, file_suffix=".comb.txt",min_successful_attempts = 2,minutes_wait = 1)
            try:
                await self.video_analysis[stream].main()
            except pytchat.exceptions.InvalidVideoIdException:
                print("aaa")
            self.analyzed_streams.append(stream)

    async def total_api_points_used(self):
        points_used_by_analysis = 0.0
        for stream in self.video_analysis.keys():
            if self.video_analysis[stream] is not None:
                points_used_by_analysis += self.video_analysis[stream].api_points_used
        return points_used_by_analysis+self.api_points_used

    def signal_handler_1(self, sig, frame):
        for stream in self.video_analysis:
            if self.video_analysis[stream]:
                self.video_analysis[stream].cancel()
        #self.running = False
        print("cancelled logging")
        points_used_by_analysis = 0.0
        for stream in self.video_analysis.keys():
            if self.video_analysis[stream] is not None:
                points_used_by_analysis += self.video_analysis[stream].api_points_used
        pts_used = points_used_by_analysis+self.api_points_used
        print("api points used:", pts_used)
        
    def signal_handler_2(self, sig, frame):
        for stream in self.video_analysis:
            if self.video_analysis[stream]:
                print(self.video_analysis[stream])

if __name__ =='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--pts','-p', action='store', type=int, default=0, help='The amout of YouTube API points already used today')
    parser.add_argument('--keyfile','-k', action='store', type=str, default="", help='The file with the API key')
    args = parser.parse_args()
    keyfilepath = str()
    if args.keyfile:
        keyfilepath = args.keyfile
    else:
        keyfilepath = "yt_api_key.txt"
    monitor = redo_recorder(args.pts,keyfilepath)
    loop = asyncio.get_event_loop()
    #loop.set_debug(True)
    #logging.getLogger("asyncio").setLevel(logging.INFO)
    #logging.basicConfig(level=logging.INFO)
    try:
        loop.run_until_complete(monitor.main())
    except asyncio.CancelledError:
        pass
