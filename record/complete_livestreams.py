#!/usr/bin/env python3
from async_record_running_livestream_superchats import SuperchatArchiver
import argparse, asyncio, json, pytchat
from datetime import datetime, timezone, timedelta
from database.psql_db import PostgresDB
from multichannel_recording_base import MultichannelRecordingBase

class redo_recorder(MultichannelRecordingBase):
    def __init__(self,exloop,chan_id,api_pts_used = 0.0, keyfilepath = "yt_api_key.txt"):
        config_files = {'yt_key': keyfilepath}
        super().__init__(exloop,128, config_files, 1, api_pts_used, 10000, 100)
        self.chan_id = chan_id
        self.videolist = []
        self.setup_logging(f"record_completer")
        with open("postgres-config.json") as pgsql_config_file:
            self.pgsql_creds = json.load(pgsql_config_file)
        self.db = PostgresDB(username=self.pgsql_creds["username"], password=self.pgsql_creds["password"],
                            host=self.pgsql_creds["host"], database=self.pgsql_creds["database"])

    async def main(self):
        self.setup_sigusr_handlers(self.loop)
        asyncio.ensure_future(self.yt_api.reset_timer())
        cutoff_date = datetime(2020, 6, 1, 0, 0, 0, 0, tzinfo=timezone.utc)
        recorded_set = await self.db.get_recorded_vid_ids(self.chan_id)
        channel_meta = await self.yt_api.async_get_channel_metadata(self.chan_id,self.loop, self.t_pool)
        upload_playlist = channel_meta["contentDetails"]["relatedPlaylists"]["uploads"]
        uploaded_videos = await self.yt_api.async_get_videos_from_playlist_id(upload_playlist,self.loop,self.t_pool)
        uploaded_videos_sort = sorted(uploaded_videos,key = lambda d: d["publish_date"], reverse = True)
        for video in uploaded_videos_sort:
            publishedDate = datetime.fromtimestamp(video["publish_date"],tz=timezone.utc)
            if publishedDate < cutoff_date:
                continue
            self.videolist.append(video["video_id"])
        channel_set = set(self.videolist)
        record_set = channel_set - recorded_set
        await self.log_output(f"recorded: {recorded_set}")
        await self.log_output(f"archived on youtube: {channel_set}")
        await self.log_output(f"to be re-recorded: {len(channel_set)}, {len(record_set)}, {record_set}")
        for entry in record_set:
            self.video_analysis.setdefault(entry,None)
            self.running_streams.append(entry)
        for stream in list(self.video_analysis.keys()):
            self.video_analysis[stream] = SuperchatArchiver(stream, self.yt_api, file_suffix=".completer.txt", min_successful_attempts = 2, logger = self.logger, t_pool = self.t_pool, minutes_wait = 0.5)
            try:
                await self.video_analysis[stream].main()
            except pytchat.exceptions.InvalidVideoIdException:
                await self.log_output("aaa")
            self.analyzed_streams.append(stream)
            await self.yt_api.sleep_by_points(request_mode=False)
        await self.log_output(f"Streams analyzed: {len(self.analyzed_streams)}")

    async def signal_handler_2(self, sig):
        worked_on = 0
        for stream in self.video_analysis:
            if self.video_analysis[stream]:
                await self.log_output(self.video_analysis[stream])
                worked_on += 1
        not_touched = len(self.video_analysis) - worked_on
        await self.log_output(f"worked on {worked_on} items out of {len(self.video_analysis)}remaining:{not_touched}")
        pts_used = await self.yt_api.get_pts_used()
        await self.log_output("api points used:", pts_used)

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
    loop = asyncio.get_event_loop()
    monitor = redo_recorder(loop,args.channel_id,args.pts,keyfilepath)
    try:
        loop.run_until_complete(monitor.main())
    except asyncio.CancelledError:
        pass
