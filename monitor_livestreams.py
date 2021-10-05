#!/usr/bin/env python3
from async_record_running_livestream_superchats import SuperchatArchiver
from youtube_api import YouTubeDataAPI
import argparse, time, os, asyncio, pytz, logging, signal, sys, concurrent.futures
from datetime import datetime, timezone, timedelta
import aiohttp
from aiohttp_requests import requests
from pytchat import config
import math

class channel_monitor:
    def __init__(self,chan_list,api_pts_used = 0.0, keyfilepath = "yt_api_key.txt", loop=None):
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
        self.chan_ids = chan_list
        self.running_streams = []
        self.analyzed_streams = []
        self.api_points = 10000.0 #available API points
        self.desired_leftover_points = 100.0 #for safety measure since the SuperchatArchiver objects will use some API points
        self.max_watched_channels = len(self.chan_ids)
        self.cost_per_request = 100.0
        #calculate how many times I can monitor all of the channels together using the Youtube search API (costs MANY API points)
        self.requests_left = math.floor((self.api_points-self.api_points_used) / (self.max_watched_channels*self.cost_per_request))
        #Calculate how long I have to wait for the next search request - trying not to exceed the 24h API usage limits
        self.sleep_dur = (60.0*60.0*24.0)/self.requests_left
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        fh = logging.FileHandler(keyfilepath+"_monitor.debuglog")
        fh.setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        dbg_formatter = config.mylogger.MyFormatter()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(dbg_formatter)
        ch.setFormatter(formatter)
        self.logger.addHandler(fh)
        self.logger.addHandler(ch)
        self.t_pool = concurrent.futures.ThreadPoolExecutor(max_workers=100)
        self.loop = loop
        

    async def main(self):
        if not self.loop:
            self.loop = asyncio.get_running_loop()
        asyncio.ensure_future(self.reset_timer()) # midnight reset timer start
        temp = await self.time_until_specified_hour(0, pytz.timezone('America/Los_Angeles'))
        self.sleep_dur = temp.total_seconds() / self.requests_left
        while self.running:
            self.running_streams.clear()
            try:
                for chan_id in self.chan_ids:
                    #catch only planned streams. Caution! API returns recently finished streams as "upcoming" too!
                    planstreams_search = await requests.get(
                        'https://youtube.googleapis.com/youtube/v3/search?part=id&channelId=' + chan_id + '&eventType=upcoming&type=video&key=' + self.yt_api_key)
                    planstreams_raw_json = await planstreams_search.json()
                    if "error" in planstreams_raw_json.keys():
                        if planstreams_raw_json['error']['code'] == 403:
                            raise ValueError("API Quota exceeded!")
                    self.api_points_used += self.cost_per_request
                    if 'items' in planstreams_raw_json.keys():
                        for streams in planstreams_raw_json['items']:
                            self.video_analysis.setdefault(streams['id']['videoId'],None)
                            self.running_streams.append(streams['id']['videoId'])
            except ValueError:
                self.api_points_used = 10000.0
                await self.log_output("API Quota exceeded!",30)
            await self.log_output(self.video_analysis)
            current_time = datetime.now(tz=pytz.timezone('Europe/Berlin')).isoformat()
            await self.log_output(list(self.video_analysis.keys()))#, planned_streams)
            if self.api_points_used < self.api_points:
                for stream in list(self.video_analysis.keys()):
                    if self.video_analysis[stream] is None and stream not in self.analyzed_streams: #because YouTube lists past streams as "upcoming" for a while after stream ends
                        try:
                            self.video_analysis[stream] = SuperchatArchiver(stream,self.yt_api_key, file_suffix=".sc-monitor.txt",logger = self.logger)
                            asyncio.ensure_future(self.video_analysis[stream].main())
                            self.analyzed_streams.append(stream)
                        except ValueError: #for some godforsaken reason, the YouTubeDataApi object throws a ValueError
                            #with a wrong error msg (claiming your API key is "incorrect")
                            #if you exceed your API quota. That's why we do the same in the code above.
                            self.api_points_used = 10000.0
                            await self.log_output("API Quota exceeded!",30)
                    else:
                        if self.video_analysis[stream] is not None and not self.video_analysis[stream].running and stream not in self.running_streams:
                            self.api_points_used += self.video_analysis[stream].api_points_used
                            self.video_analysis.pop(stream)
            total_points_used = await self.total_api_points_used()
            #If we somehow used too many API points, calculate waiting time between now an midnight pacific time
            if total_points_used >= (self.api_points-self.desired_leftover_points):
                time_now = datetime.now(tz=pytz.timezone('America/Los_Angeles'))
                await self.log_output(time_now.isoformat())
                resume_at = await self.next_specified_hour_datetime(0,pytz.timezone('America/Los_Angeles'))
                t_delta = resume_at-time_now
                self.sleep_dur = t_delta.total_seconds()
                self.requests_left = 0
                self.reset_used = True
            else:
                # Calculate how long I have to wait for the next search request
                # trying not to exceed the 24h API usage limits while also accounting for time already passed since last
                # API point reset (which happens at midnight pacific time)
                self.requests_left = math.floor((self.api_points - self.api_points_used) / (self.max_watched_channels * self.cost_per_request))
                if self.requests_left > 0:
                    temp = await self.time_until_specified_hour(0,pytz.timezone('America/Los_Angeles'))
                    self.sleep_dur = temp.total_seconds()/self.requests_left
                    resume_at = datetime.now(tz=pytz.timezone('Europe/Berlin'))+timedelta(seconds=self.sleep_dur)
                else:
                    time_now = datetime.now(tz=pytz.timezone('America/Los_Angeles'))
                    resume_at = await self.next_specified_hour_datetime(0,pytz.timezone('America/Los_Angeles'))
                    t_delta = resume_at-time_now
                    self.sleep_dur = t_delta.total_seconds()
            await self.log_output('sleeping again for ' + str(self.sleep_dur/60) + ' minutes')
            await self.log_output('approx. '+str(self.api_points-self.api_points_used)+' points left')
            await self.log_output((self.requests_left, "requests left"))
            awake_at = resume_at.astimezone(pytz.timezone('Europe/Berlin'))
            await self.log_output('next run at: ' + awake_at.isoformat() + " Berlin Time")
            await asyncio.sleep(self.sleep_dur)
            #When midnight passes, do this API point reset
            if self.reset_used:
                self.api_points_used = 0
                self.requests_left = math.floor(
                    (self.api_points - self.api_points_used) / (self.max_watched_channels * self.cost_per_request))
                await self.log_output('used points reset at ' + datetime.now(tz=pytz.timezone('Europe/Berlin')).isoformat() + " Berlin time")
                self.reset_used = False

    async def next_specified_hour_datetime(self,w_hour,tzinfo_p):
        time_now = datetime.now(tz=tzinfo_p)
        if time_now.hour >= w_hour:
            next_day = time_now+timedelta(days=1)
            new_time = next_day.replace(hour=w_hour, minute=0, second=1, microsecond=1)
        else:
            new_time = time_now.replace(hour=w_hour,minute=0, second=1, microsecond=1)
        return new_time

    async def last_specified_hour_datetime(self,w_hour,tzinfo_p):
        time_now = datetime.now(tz=tzinfo_p)
        if time_now.hour > w_hour:
            next_day = time_now - timedelta(days=1)
            new_time = next_day.replace(hour=w_hour, minute=0, second=0, microsecond=0)
        else:
            new_time = time_now.replace(hour=w_hour,minute=0, second=0, microsecond=0)
        return new_time

    async def time_until_specified_hour(self, w_hour, tzinfo_p):
        time_now = datetime.now(tz=tzinfo_p)
        reset_at = await self.next_specified_hour_datetime(w_hour, tzinfo_p)
        t_delta = reset_at - time_now
        return t_delta

    async def time_before_specified_hour(self, w_hour, tzinfo_p):
        time_now = datetime.now(tz=tzinfo_p)
        old_time = await self.last_specified_hour_datetime(w_hour, tzinfo_p)
        t_delta = time_now - old_time
        return t_delta

    async def reset_timer(self, w_hour = 0, tzinfo_p = pytz.timezone('America/Los_Angeles')):
        time_until_reset = await self.time_until_specified_hour(w_hour,tzinfo_p)
        while True:
            await asyncio.sleep(time_until_reset.total_seconds())
            await self.log_output(("midnight reset taking place, old points used:",self.api_points_used))
            self.api_points_used = 0
            await asyncio.sleep(1)
            time_until_reset = await self.time_until_specified_hour(w_hour, tzinfo_p)

    async def total_api_points_used(self):
        points_used_by_analysis = 0.0
        for stream in self.video_analysis.keys():
            if self.video_analysis[stream] is not None:
                points_used_by_analysis += self.video_analysis[stream].api_points_used
        return points_used_by_analysis+self.api_points_used
    
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

    def signal_handler_1(self, sig, frame):
        for stream in self.video_analysis:
            if self.video_analysis[stream]:
                self.video_analysis[stream].cancel()
        #self.running = False
        self.logger.log(10,"cancelled logging")
        points_used_by_analysis = 0.0
        for stream in self.video_analysis.keys():
            if self.video_analysis[stream] is not None:
                points_used_by_analysis += self.video_analysis[stream].api_points_used
        pts_used = points_used_by_analysis+self.api_points_used
        self.logger.log(20,"api points used: " + str(pts_used))
        
    def signal_handler_2(self, sig, frame):
        for stream in self.video_analysis:
            if self.video_analysis[stream]:
                self.logger.log(20,str(self.video_analysis[stream]))

if __name__ =='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('channel_id', metavar='N', type=str, nargs='+', help='The YouTube channel IDs')
    parser.add_argument('--pts','-p', action='store', type=int, default=0, help='The amout of YouTube API points already used today')
    parser.add_argument('--keyfile','-k', action='store', type=str, default="", help='The file with the API key')
    args = parser.parse_args()
    chan_ids = args.channel_id
    max_watched_channels = len(chan_ids)
    print('# of channels bein watched:',max_watched_channels)
    keyfilepath = str()
    if args.keyfile:
        keyfilepath = args.keyfile
    else:
        keyfilepath = "yt_api_key.txt"
    loop = asyncio.get_event_loop()
    monitor = channel_monitor(chan_ids,args.pts,keyfilepath,loop)
    #loop.set_debug(True)
    #logging.getLogger("asyncio").setLevel(logging.INFO)
    #logging.basicConfig(level=logging.INFO)
    try:
        loop.run_until_complete(monitor.main())
    except asyncio.CancelledError:
        pass
