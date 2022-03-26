#!/usr/bin/env python3
from async_record_running_livestream_superchats import SuperchatArchiver
from youtube_api import YouTubeDataAPI
import argparse, time, os, asyncio, pytz, logging, signal, sys, concurrent.futures, traceback, requests
from datetime import datetime, timezone, timedelta
import aiohttp
from pytchat import config
import math

class channel_monitor:
    def __init__(self,chan_file_path,yt_api_pts_used = 0.0, yt_keyfilepath = "yt_api_key.txt", holo_api_pts_used = 0.0, holodex_keyfilepath = "holodex_key.txt", loop=None):
        self.running = True
        self.reset_used = False
        self.yt_api_key = "####"
        keyfile = open(yt_keyfilepath, "r")
        self.yt_api_key = keyfile.read()
        keyfile.close()
        keyfile = open(holodex_keyfilepath,"r")
        self.holodex_key = keyfile.read().replace("\n", "")
        keyfile.close()
        chan_file = open(chan_file_path, "r")
        self.chan_ids = set([line.rstrip() for line in chan_file])
        chan_file.close()
        self.config_files = {'yt_key': yt_keyfilepath,
                            'holodex': holodex_keyfilepath,
                            'channels': chan_file_path}
        max_watched_channels = len(self.chan_ids)
        print('# of channels bein watched:',max_watched_channels)
        self.api_points_used = yt_api_pts_used
        self.holo_api_points_used = holo_api_pts_used
        self.video_analysis = {}
        self.running_streams = []
        self.analyzed_streams = []
        self.api_points = 10000.0 #available API points
        self.holodex_api_points = (24*60/10)*10
        self.desired_leftover_points = 100.0 #for safety measure since the SuperchatArchiver objects will use some API points
        self.max_watched_channels = len(self.chan_ids)
        self.cost_per_request = 10.0
        #calculate how many times I can monitor all of the channels together using the Holodex API (costs MANY API points)
        self.requests_left = math.floor((self.holodex_api_points-self.holo_api_points_used) / self.cost_per_request)
        #Calculate how long I have to wait for the next search request - trying not to exceed the 24h API usage limits
        self.sleep_dur = (60.0*60.0*24.0)/self.requests_left
        self.min_sleep = 300.0
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        fh = logging.FileHandler(chan_file_path+"_monitor.debuglog")
        fh.setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        dbg_formatter = config.mylogger.MyFormatter()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(dbg_formatter)
        ch.setFormatter(formatter)
        self.logger.addHandler(fh)
        self.logger.addHandler(ch)
        self.t_pool = concurrent.futures.ThreadPoolExecutor(max_workers=300)
        self.loop = loop
        

    async def main(self):
        if not self.loop:
            self.loop = asyncio.get_running_loop()
        loop.add_signal_handler(signal.SIGHUP,lambda signame="SIGHUP": asyncio.create_task(self.reload_config(signame)))
        loop.add_signal_handler(signal.SIGUSR1,lambda signame="SIGUSR1": asyncio.create_task(self.signal_handler_1(signame)))
        loop.add_signal_handler(signal.SIGUSR2,lambda signame="SIGUSR2": asyncio.create_task(self.signal_handler_2(signame)))
        asyncio.ensure_future(self.reset_timer()) # midnight reset timer start
        temp = await self.time_until_specified_hour(0, pytz.timezone('America/Los_Angeles'))
        self.sleep_dur = max(temp.total_seconds() / self.requests_left,self.min_sleep)
        while self.running:
            self.running_streams.clear()
            try:
                api_endpoint = "https://holodex.net/api/v2/users/live"
                async with aiohttp.ClientSession(headers = {"X-APIKEY": self.holodex_key}) as session:
                    apiparams = {"channels": ",".join(self.chan_ids)}
                    async with session.get(api_endpoint, params=apiparams) as resp:
                        self.holo_api_points_used += self.cost_per_request
                        if resp.status == 200:
                            streams_raw_json = await resp.json()
                            for streams in streams_raw_json:
                                if "membersonly" not in streams.get("topic_id",[]):
                                    self.video_analysis.setdefault(streams['id'],None)
                                    self.running_streams.append(streams['id'])
            except ValueError as v:
                await self.log_output("API Problem!",30)
                await self.log_output(str(v),30)
            except Exception as e:
                await self.log_output("live stream lookup failed!",30)
                await self.log_output(str(e),30)
            await self.log_output(self.video_analysis)
            current_time = datetime.now(tz=pytz.timezone('Europe/Berlin')).isoformat()
            await self.log_output(list(self.video_analysis.keys()))#, planned_streams)
            total_points_used = await self.total_api_points_used()
            if total_points_used < self.api_points:
                for stream in list(self.video_analysis.keys()):
                    if self.video_analysis[stream] is None and stream not in self.analyzed_streams: #because YouTube lists past streams as "upcoming" for a while after stream ends
                        try:
                            self.video_analysis[stream] = SuperchatArchiver(stream,self.yt_api_key, file_suffix=".sc-monitor.txt",logger = self.logger, t_pool = self.t_pool)
                            asyncio.ensure_future(self.video_analysis[stream].main())
                            self.analyzed_streams.append(stream)
                            await asyncio.sleep(0.100)
                        except ValueError: #for some godforsaken reason, the YouTubeDataApi object throws a ValueError
                            #with a wrong error msg (claiming your API key is "incorrect")
                            #if you exceed your API quota. That's why we do the same in the code above.
                            self.api_points_used = 10000.0
                            await self.log_output("API Quota exceeded!",30)
                            break
                        except requests.exceptions.ConnectionError as e:
                            await self.log_output("Connection error, retrying with next scan! Video ID: "+stream,30)
                            await self.log_output(str(e),30)
                    else:
                        if self.video_analysis[stream] is not None and not self.video_analysis[stream].running and stream not in self.running_streams:
                            self.api_points_used += await self.video_analysis[stream].pts_used_today()
                            self.video_analysis.pop(stream)
            total_points_used = await self.total_api_points_used()
            #If we somehow used too many API points, calculate waiting time between now an midnight pacific time
            if total_points_used >= (self.api_points-self.desired_leftover_points) or self.holo_api_points_used >= self.holodex_api_points:
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
                self.requests_left = await self.calc_requests_left()
                if self.requests_left > 0:
                    temp = await self.time_until_specified_hour(0,pytz.timezone('America/Los_Angeles'))
                    self.sleep_dur = max(temp.total_seconds()/self.requests_left,self.min_sleep)
                    resume_at = datetime.now(tz=pytz.timezone('Europe/Berlin'))+timedelta(seconds=self.sleep_dur)
                else:
                    time_now = datetime.now(tz=pytz.timezone('America/Los_Angeles'))
                    resume_at = await self.next_specified_hour_datetime(0,pytz.timezone('America/Los_Angeles'))
                    t_delta = resume_at-time_now
                    self.sleep_dur = t_delta.total_seconds()
                    self.reset_used = True
            await self.log_output('sleeping again for ' + str(self.sleep_dur/60) + ' minutes')
            await self.log_output('approx. '+str(total_points_used)+' YouTube points used')
            await self.log_output('approx. '+str(self.holodex_api_points-self.holo_api_points_used)+' Holodex points left')
            await self.log_output((self.requests_left, "requests left"))
            awake_at = resume_at.astimezone(pytz.timezone('Europe/Berlin'))
            await self.log_output('next run at: ' + awake_at.isoformat() + " Berlin Time")
            await asyncio.sleep(self.sleep_dur)
            #When midnight passes, do this API point reset
            if self.reset_used:
                self.api_points_used = 0
                self.holo_api_points_used = 0
                self.requests_left = await self.calc_requests_left()
                await self.log_output('used points reset at ' + datetime.now(tz=pytz.timezone('Europe/Berlin')).isoformat() + " Berlin time")
                self.reset_used = False

    async def next_specified_hour_datetime(self,w_hour,tzinfo_p):
        time_now = datetime.now(tz=tzinfo_p)
        if time_now.hour >= w_hour:
            next_day = await self.add_day(time_now)
            new_time = next_day.replace(hour=w_hour, minute=0, second=0, microsecond=0)
        else:
            new_time = time_now.replace(hour=w_hour,minute=0, second=0, microsecond=0)
        return new_time

    async def last_specified_hour_datetime(self,w_hour,tzinfo_p):
        time_now = datetime.utcnow().replace(tzinfo=pytz.utc)
        if time_now.hour > w_hour:
            utc_last_day = time_now - timedelta(days=1)
            last_day = utc_last_day.astimezone(tzinfo_p)
            new_time = last_day.replace(hour=w_hour, minute=0, second=0, microsecond=0)
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
    
    async def add_day(self,today):
        today_utc = today.astimezone(timezone.utc)
        tz = today.tzinfo
        tomorrow_utc = today_utc + timedelta(days=1)
        tomorrow_utc_tz = tomorrow_utc.astimezone(tz)
        tomorrow_utc_tz = tomorrow_utc_tz.replace(hour=today.hour,
                                                  minute=today.minute,
                                                  second=today.second)
        if tomorrow_utc_tz - today < timedelta(hours = 23):
            tomorrow_utc_tz += timedelta(days = 1)
            tomorrow_utc_tz = tomorrow_utc_tz.replace(hour=today.hour,
                                                  minute=today.minute,
                                                  second=today.second)
        return tomorrow_utc_tz
    

    async def reset_timer(self, w_hour = 0, tzinfo_p = pytz.timezone('America/Los_Angeles')):
        time_until_reset = await self.time_until_specified_hour(w_hour,tzinfo_p)
        while True:
            await asyncio.sleep(time_until_reset.total_seconds())
            await self.log_output(("midnight reset taking place, old points used:",self.api_points_used))
            self.api_points_used = 0
            self.holo_api_points_used = 0
            await asyncio.sleep(1)
            time_until_reset = await self.time_until_specified_hour(w_hour, tzinfo_p)

    async def total_api_points_used(self):
        points_used_by_analysis = 0.0
        compare_time = await self.last_specified_hour_datetime(0,pytz.timezone('America/Los_Angeles'))
        for stream in self.video_analysis.keys():
            if self.video_analysis[stream] is not None:
                points_used_by_analysis += sum(i[0] for i in self.video_analysis[stream].api_points_log if i[1] >= compare_time)
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
        
    async def calc_requests_left(self):
        return math.floor((self.holodex_api_points-self.holo_api_points_used) / self.cost_per_request)

    async def signal_handler_1(self, sig):
        for stream in self.video_analysis:
            if self.video_analysis[stream]:
                self.video_analysis[stream].cancel()
        #self.running = False
        await self.log_output("cancelled logging")
        pts_used = await self.total_api_points_used()
        await self.log_output("youtube api points used: " + str(pts_used))
        await self.log_output("holodex api points used: " + str(self.holo_api_points_used))
        
    async def signal_handler_2(self, sig):
        for stream in self.video_analysis:
            if self.video_analysis[stream]:
                await self.log_output(str(self.video_analysis[stream]))
    
    async def reload_config(self, sig):
        await self.log_output('reloading configuration')
        keyfile = open(self.config_files['yt_key'], "r")
        self.yt_api_key = keyfile.read()
        keyfile.close()
        keyfile = open(self.config_files['holodex'],"r")
        self.holodex_key = keyfile.read().replace("\n", "")
        keyfile.close()
        chan_file = open(self.config_files['channels'], "r")
        self.chan_ids = set([line.rstrip() for line in chan_file])
        chan_file.close()
        max_watched_channels = len(self.chan_ids)
        await self.log_output('# of channels bein watched: '+str(max_watched_channels))

if __name__ =='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('channel_file', metavar='N', type=str, help='The file containing YouTube channel IDs')
    parser.add_argument('--yt_pts','-ytp', action='store', type=int, default=0, help='The amout of YouTube API points already used today')
    parser.add_argument('--ytkeyfile','-yt_k', action='store', type=str, default="", help='The file with the YouTube API key')
    parser.add_argument('--holo_pts','-hdp', action='store', type=int, default=0, help='The amout of Holodex API points already used today')
    parser.add_argument('--holokeyfile','-h_k', action='store', type=str, default="", help='The file with the Holodex API key')
    args = parser.parse_args()
    chan_file_path = args.channel_file
    yt_keyfilepath = str()
    if args.ytkeyfile:
        yt_keyfilepath = args.ytkeyfile
    else:
        yt_keyfilepath = "yt_api_key.txt"
    holo_keyfilepath = str()
    if args.holokeyfile:
        holo_keyfilepath = args.holokeyfile
    else:
        holo_keyfilepath = "holodex_key.txt"
    loop = asyncio.get_event_loop()
    monitor = channel_monitor(chan_file_path,args.yt_pts,yt_keyfilepath,args.holo_pts,holo_keyfilepath,loop)
    try:
        loop.run_until_complete(monitor.main())
    except asyncio.CancelledError:
        pass
