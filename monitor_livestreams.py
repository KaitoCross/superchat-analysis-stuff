from async_record_running_livestream_superchats import SuperchatArchiver
from youtube_api import YouTubeDataAPI
import argparse, time, os, asyncio, pytz, logging, signal, sys
from datetime import datetime, timezone, timedelta
import aiohttp
from aiohttp_requests import requests
import math

class channel_monitor:
    def __init__(self,chan_list,api_pts_used = 0.0, keyfilepath):
        self.running = True
        self.reset_used = False
        signal.signal(signal.SIGUSR1, self.signal_handler)
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

    async def main(self):
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
                print("API Quota exceeded!")
            print(self.video_analysis)
            current_time = datetime.now(tz=pytz.timezone('Europe/Berlin')).isoformat()
            print(current_time,list(self.video_analysis.keys()))#, planned_streams)
            if self.api_points_used < self.api_points:
                for stream in list(self.video_analysis.keys()):
                    if self.video_analysis[stream] is None and stream not in self.analyzed_streams: #because YouTube lists past streams as "upcoming" for a while after stream ends
                        try:
                            self.video_analysis[stream] = SuperchatArchiver(stream,self.yt_api_key, file_suffix=".sc-monitor.txt")
                            asyncio.ensure_future(self.video_analysis[stream].main())
                            self.analyzed_streams.append(stream)
                        except ValueError: #for some godforsaken reason, the YouTubeDataApi object throws a ValueError
                            #with a wrong error msg (claiming your API key is "incorrect")
                            #if you exceed your API quota. That's why we do the same in the code above.
                            self.api_points_used = 10000.0
                            print("API Quota exceeded!")
                    else:
                        if self.video_analysis[stream] is not None and not self.video_analysis[stream].running and stream not in self.running_streams:
                            self.api_points_used += self.video_analysis[stream].api_points_used
                            self.video_analysis.pop(stream)
            total_points_used = await self.total_api_points_used()
            #If we somehow used too many API points, calculate waiting time between now an midnight pacific time
            if total_points_used >= (self.api_points-self.desired_leftover_points):
                time_now = datetime.now(tz=pytz.timezone('America/Los_Angeles'))
                print(time_now.isoformat())
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
                temp = await self.time_until_specified_hour(0,pytz.timezone('America/Los_Angeles'))
                self.sleep_dur = temp.total_seconds()/self.requests_left
                resume_at = datetime.now(tz=pytz.timezone('Europe/Berlin'))+timedelta(seconds=self.sleep_dur)
            print('sleeping again for ' + str(self.sleep_dur/60) + ' minutes')
            print('approx. '+str(self.api_points-self.api_points_used)+' points left')
            print(self.requests_left, "requests left")
            awake_at = resume_at.astimezone(pytz.timezone('Europe/Berlin'))
            print('next run at: ' + awake_at.isoformat() + " Berlin Time")
            await asyncio.sleep(self.sleep_dur)
            #When midnight passes, do this API point reset
            if self.reset_used:
                self.api_points_used = 0
                self.requests_left = math.floor(
                    (self.api_points - self.api_points_used) / (self.max_watched_channels * self.cost_per_request))
                print('used points reset at ' + datetime.now(tz=pytz.timezone('Europe/Berlin')).isoformat() + " Berlin time")
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
            print("midnight reset taking place, old points used:",self.api_points_used)
            self.api_points_used = 0
            await asyncio.sleep(1)
            time_until_reset = await self.time_until_specified_hour(w_hour, tzinfo_p)

    async def total_api_points_used(self):
        points_used_by_analysis = 0.0
        for stream in self.video_analysis.keys():
            if self.video_analysis[stream] is not None:
                points_used_by_analysis += self.video_analysis[stream].api_points_used
        return points_used_by_analysis+self.api_points_used

    def signal_handler(self, sig, frame):
        for stream in self.video_analysis:
            if stream:
                self.video_analysis[stream].cancel()
        #self.running = False
        print("cancelled logging")
        print("api points used:", self.api_points_used)

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
    monitor = channel_monitor(chan_ids,args.pts,keyfilepath)
    loop = asyncio.get_event_loop()
    #loop.set_debug(True)
    #logging.getLogger("asyncio").setLevel(logging.INFO)
    #logging.basicConfig(level=logging.INFO)
    try:
        loop.run_until_complete(monitor.main())
    except asyncio.CancelledError:
        pass
