#!/usr/bin/env python3
from async_record_running_livestream_superchats import SuperchatArchiver
import argparse, asyncio
from datetime import datetime, timezone
from multichannel_recording_base import MultichannelRecordingBase

class channel_archiver(MultichannelRecordingBase):
    def __init__(self,chan_list,api_pts_used = 0.0, keyfilepath = "yt_api_key.txt", exloop=None):
        config_files = {'yt_key': keyfilepath}
        self.chan_ids = chan_list
        max_watched_channels = len(self.chan_ids)
        super().__init__(exloop,100, config_files, max_watched_channels, api_pts_used, 300, 10)
        self.setup_logging(f"channel_archiver")
        self.videolist = {}

    async def main(self):
        if not self.loop:
            self.loop = asyncio.get_running_loop()
        self.setup_sigusr_handlers(self.loop)
        asyncio.ensure_future(self.yt_api.reset_timer()) # midnight reset timer start
        cutoff_date = datetime(2020, 6, 1, 0, 0, 0, 0, tzinfo=timezone.utc)
        await self.log_output("Collecting videos..")
        for id in self.chan_ids:
            await self.log_output(id)
            channel_meta = await self.yt_api.async_get_channel_metadata(id, self.loop, self.t_pool)
            upload_playlist = channel_meta["contentDetails"]["relatedPlaylists"]["uploads"]
            uploaded_videos = await self.yt_api.async_get_videos_from_playlist_id(upload_playlist, self.loop, self.t_pool)
            uploaded_videos_sort = sorted(uploaded_videos,key = lambda d: d["publish_date"])
            for video in uploaded_videos_sort:
                publishedDate = datetime.fromtimestamp(video["publish_date"],tz=timezone.utc)
                if publishedDate < cutoff_date:
                    continue
                self.videolist[video["video_id"]] = {"channelId": video["channel_id"]}
        await self.log_output(self.videolist)
        while self.running:
            await self.log_output("collecting superchats")
            for stream in self.videolist.keys():
                await self.wait_for_points()
                await self.log_output(stream)
                self.video_analysis[stream] = SuperchatArchiver(stream,self.yt_api, file_suffix=".retrospective-archive.txt",logger = self.logger)
                await self.video_analysis[stream].main()
                self.analyzed_streams.append(stream)
            self.running = False

                
    async def wait_for_points(self):
        await self.yt_api.sleep_by_points(request_mode=False)

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
    monitor = channel_archiver(chan_ids, args.pts, keyfilepath, loop)
    #loop.set_debug(True)
    #logging.getLogger("asyncio").setLevel(logging.INFO)
    #logging.basicConfig(level=logging.INFO)
    try:
        loop.run_until_complete(monitor.main())
    except asyncio.CancelledError:
        pass
