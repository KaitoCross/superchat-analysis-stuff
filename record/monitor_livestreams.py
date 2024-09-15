#!/usr/bin/env python3
from async_record_running_livestream_superchats import SuperchatArchiver
from data_apis.HolodexDataAPI import HolodexDataAPI
from multichannel_recording_base import MultichannelRecordingBase
import argparse, asyncio, pytz, signal, concurrent.futures, traceback, requests
from datetime import datetime, timezone, timedelta

class channel_monitor(MultichannelRecordingBase):
    def __init__(self,chan_file_path, holodex_mode = False, api_pts_used = 0.0, keyfilepath = "yt_api_key.txt",
                 holo_api_pts_used = 0.0, holo_keyfilepath = "holodex_key.txt", exloop=None):
        config_files = {'yt_key': keyfilepath,
                            'holodex': holo_keyfilepath,
                            'channels': chan_file_path}
        self.holo_api_key = "####"
        self.load_channel_list(chan_file_path)
        max_watched_channels = len(self.chan_ids)
        super().__init__(exloop, 300, config_files, max_watched_channels, api_pts_used)
        self.holodex_mode = holodex_mode
        self.holodex_api = HolodexDataAPI(self.holo_api_key, max_watched_channels, self.reset_tz, self.log_output, holo_api_pts_used)
        self.primary_api = self.holodex_api if self.holodex_mode else self.yt_api
        print(f'# of channels bein watched: {max_watched_channels}')
        self.setup_logging("livestream_monitor")
        

    async def main(self):
        if not self.loop:
            self.loop = asyncio.get_running_loop()
        self.loop.add_signal_handler(signal.SIGHUP,lambda signame="SIGHUP": asyncio.create_task(self.reload_config(signame)))
        self.setup_sigusr_handlers(self.loop)
        asyncio.ensure_future(self.yt_api.reset_timer()) # midnight reset timer start
        asyncio.ensure_future(self.holodex_api.reset_timer())
        self.sleep_dur = await self.primary_api.get_sleep_dur()
        while self.running:
            self.running_streams.clear()
            stream_id_set = await self.primary_api.get_live_streams_multichannel(self.chan_ids)
            for stream_id in stream_id_set:
                self.video_analysis.setdefault(stream_id, None)
                self.running_streams.append(stream_id)
            await self.log_output(self.video_analysis)
            await self.log_output(list(self.video_analysis.keys()))
            if await self.yt_api.get_pts_used() < self.yt_api.points and not await self.holodex_api.points_depleted():
                for stream in list(self.video_analysis.keys()):
                    if self.video_analysis[stream] is None and stream not in self.analyzed_streams: #because YouTube lists past streams as "upcoming" for a while after stream ends
                        try:
                            self.video_analysis[stream] = SuperchatArchiver(stream,self.yt_api, file_suffix=".sc-monitor.txt",logger = self.logger, t_pool = self.t_pool)
                            asyncio.ensure_future(self.video_analysis[stream].main())
                            self.analyzed_streams.append(stream)
                            await asyncio.sleep(0.100)
                        except ValueError: #for some godforsaken reason, the YouTubeDataApi object throws a ValueError
                            #with a wrong error msg (claiming your API key is "incorrect")
                            #if you exceed your API quota. That's why we do the same in the code above.
                            await self.yt_api.mark_all_used()
                            await self.holodex_api.mark_all_used()
                            await self.log_output("API Quota exceeded!",30)
                            break
                        except requests.exceptions.ConnectionError as e:
                            await self.log_output(f"Connection error, retrying with next scan! Video ID: {stream}",30)
                            await self.log_output(str(e),30)
                    else:
                        if self.video_analysis[stream] is not None and not self.video_analysis[stream].running and stream not in self.running_streams:
                            self.video_analysis[stream] = None
                            self.video_analysis.pop(stream)
            await self.primary_api.sleep_by_points(0, await self.yt_api.points_depleted() if self.holodex_mode else False,
                                                   self.yt_api.log_used if self.holodex_mode else None,
                                                   self.yt_api.reset_pts if self.holodex_mode else None)

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

    def load_channel_list(self, chan_file_path):
        with open(chan_file_path, "r") as chan_file:
            self.chan_ids = {line.rstrip() for line in chan_file}

    async def reload_config(self, sig):
        await self.log_output('reloading configuration')
        self.load_config()
        self.load_channel_list()
        self.yt_api.set_api_key(self.yt_api_key)
        self.holodex_api.set_api_key(self.holo_api_key)
        max_watched_channels = len(self.chan_ids)
        await self.log_output(f'# of channels bein watched: {max_watched_channels}')

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
