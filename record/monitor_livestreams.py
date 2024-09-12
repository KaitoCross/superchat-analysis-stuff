#!/usr/bin/env python3
from async_record_running_livestream_superchats import SuperchatArchiver
from data_apis.YouTubeDataAPI import YouTubeDataAPI
from data_apis.HolodexDataAPI import HolodexDataAPI
import argparse, asyncio, pytz, logging, logging.handlers, signal, concurrent.futures, traceback, requests
from datetime import datetime, timezone, timedelta
from pytchat import config

class channel_monitor:
    def __init__(self,chan_file_path, holodex_mode = False, api_pts_used = 0.0, keyfilepath = "yt_api_key.txt",
                 holo_api_pts_used = 0.0, holo_keyfilepath = "holodex_key.txt", loop=None):
        self.running = True
        self.holodex_mode = holodex_mode
        self.yt_api_key = self.holo_api_key = "####"
        self.config_files = {'yt_key': keyfilepath,
                            'holodex': holo_keyfilepath,
                            'channels': chan_file_path}
        self.load_config()
        self.video_analysis = {}
        max_watched_channels = len(self.chan_ids)
        self.reset_tz = pytz.timezone('America/Los_Angeles')
        self.yt_api = YouTubeDataAPI(self.yt_api_key, max_watched_channels, self.reset_tz, self.log_output, api_pts_used)
        self.holodex_api = HolodexDataAPI(self.holo_api_key, max_watched_channels, self.reset_tz, self.log_output, holo_api_pts_used)
        self.primary_api = self.holodex_api if self.holodex_mode else self.yt_api
        print(f'# of channels bein watched: {max_watched_channels}')
        self.running_streams = []
        self.analyzed_streams = []
        self.setup_logging()
        self.t_pool = concurrent.futures.ThreadPoolExecutor(max_workers=300)
        self.loop = loop

    def setup_logging(self):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        fh = logging.handlers.TimedRotatingFileHandler("logs/livestream_monitor.debuglog", when='midnight', utc=True, backupCount=183)
        fh.setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        dbg_formatter = config.mylogger.MyFormatter()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(dbg_formatter)
        ch.setFormatter(formatter)
        self.logger.addHandler(fh)
        self.logger.addHandler(ch)
        

    async def main(self):
        if not self.loop:
            self.loop = asyncio.get_running_loop()
        loop.add_signal_handler(signal.SIGHUP,lambda signame="SIGHUP": asyncio.create_task(self.reload_config(signame)))
        loop.add_signal_handler(signal.SIGUSR1,lambda signame="SIGUSR1": asyncio.create_task(self.signal_handler_1(signame)))
        loop.add_signal_handler(signal.SIGUSR2,lambda signame="SIGUSR2": asyncio.create_task(self.signal_handler_2(signame)))
        asyncio.ensure_future(self.reset_timers()) # midnight reset timer start
        self.sleep_dur = self.primary_api.get_sleep_dur()
        while self.running:
            self.running_streams.clear()
            stream_id_set = await self.primary_api.get_live_streams_multichannel(self.chan_ids)
            for stream_id in stream_id_set:
                self.video_analysis.setdefault(stream_id, None)
                self.running_streams.append(stream_id)
            await self.log_output(self.video_analysis)
            await self.log_output(list(self.video_analysis.keys()))
            total_yt_points_used = await self.total_yt_api_points_used()
            if total_yt_points_used < self.yt_api.points and not self.holodex_api.points_depleted():
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
                            self.yt_api.mark_all_used()
                            self.holodex_api.mark_all_used()
                            await self.log_output("API Quota exceeded!",30)
                            break
                        except requests.exceptions.ConnectionError as e:
                            await self.log_output(f"Connection error, retrying with next scan! Video ID: {stream}",30)
                            await self.log_output(str(e),30)
                    else:
                        if self.video_analysis[stream] is not None and not self.video_analysis[stream].running and stream not in self.running_streams:
                            self.yt_api.points += await self.yt_pts_used_today(self.video_analysis[stream])
                            self.video_analysis[stream] = None
                            self.video_analysis.pop(stream)
            pts_ext = await self.api_points_used_externally()
            await self.primary_api.sleep_by_points(pts_ext, self.yt_api.points_depleted(pts_ext) if self.holodex_mode else False,
                                                   self.yt_api.log_used if self.holodex_mode else None)

    async def last_specified_hour_datetime(self,w_hour,tzinfo_p):
        time_now = datetime.now(tz=timezone.utc)
        if time_now.hour > w_hour:
            utc_last_day = time_now - timedelta(days=1)
            last_day = utc_last_day.astimezone(tzinfo_p)
            new_time = last_day.replace(hour=w_hour, minute=0, second=0, microsecond=0)
        else:
            new_time = time_now.replace(hour=w_hour,minute=0, second=0, microsecond=0)
        return new_time

    async def time_before_specified_hour(self, w_hour, tzinfo_p):
        time_now = datetime.now(tz=tzinfo_p)
        old_time = await self.last_specified_hour_datetime(w_hour, tzinfo_p)
        t_delta = time_now - old_time
        return t_delta
    
    async def api_points_used_externally(self):
        points_used_by_analysis = 0.0
        compare_time = await self.last_specified_hour_datetime(0,self.reset_tz)
        for stream in self.video_analysis.keys():
            if self.video_analysis[stream] is not None:
                points_used_by_analysis += sum(i[0] for i in self.video_analysis[stream].api_points_log if i[1] >= compare_time)
        return points_used_by_analysis

    async def total_yt_api_points_used(self):
        return await self.api_points_used_externally() + self.yt_api.points_used
    
    async def yt_pts_used_today(self, stream):
        points_used_by_analysis = 0.0
        compare_time = await self.last_specified_hour_datetime(0,self.reset_tz)
        points_used_by_analysis += sum(i[0] for i in stream.api_points_log if i[1] >= compare_time)
        return points_used_by_analysis
    
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

    async def signal_handler_1(self, sig):
        for stream in self.video_analysis:
            if self.video_analysis[stream]:
                self.video_analysis[stream].cancel()
        #self.running = False
        await self.log_output("cancelled logging")
        pts_used = await self.total_yt_api_points_used()
        await self.log_output(f"youtube api points used: {pts_used}")
        self.logger.log(20,f"api points used: {pts_used}")
        
    async def signal_handler_2(self, sig):
        for stream in self.video_analysis:
            if self.video_analysis[stream]:
                await self.log_output(str(self.video_analysis[stream]))

    def load_config(self):
        with open(self.config_files['yt_key'], "r") as keyfile:
            self.yt_api_key = keyfile.read()
        if self.config_files['holodex']:
            with open(self.config_files['holodex'],"r") as keyfile:
                self.holo_api_key = keyfile.read().replace("\n", "")
        with open(self.config_files['channels'], "r") as chan_file:
            self.chan_ids = {line.rstrip() for line in chan_file}

    async def reload_config(self, sig):
        await self.log_output('reloading configuration')
        self.load_config()
        self.yt_api.set_api_key(self.yt_api_key)
        self.holodex_api.set_api_key(self.holo_api_key)
        max_watched_channels = len(self.chan_ids)
        await self.log_output(f'# of channels bein watched: {max_watched_channels}')

    async def reset_timers(self):
        await self.yt_api.reset_pts()
        await self.holodex_api.reset_pts()

if __name__ =='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('channel_file', metavar='N', type=str, help='The file containing YouTube channel IDs')
    parser.add_argument('--pts','-p', action='store', type=int, default=0, help='The amount of YouTube API points already used today')
    parser.add_argument('--keyfile','-k', action='store', type=str, default="yt_api_key.txt", help='The file with the YouTube API key')
    parser.add_argument('--holo_pts', '-hp', action='store', type=int, default=0, help='The amount of Holodex API points already used today')
    parser.add_argument('--holo_keyfile', '-hk', action='store', type=str, default="", help='The file with the Holodex API key')
    args = parser.parse_args()
    chan_file_path = args.channel_file
    keyfilepath = args.keyfile
    loop = asyncio.get_event_loop()
    holodex_mode = bool(args.holo_keyfile)
    monitor = channel_monitor(chan_file_path,holodex_mode,args.pts,keyfilepath,args.holo_pts,args.holo_keyfile,loop)
    try:
        loop.run_until_complete(monitor.main())
    except asyncio.CancelledError:
        pass
