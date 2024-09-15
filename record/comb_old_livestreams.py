#!/usr/bin/env python3
from async_record_running_livestream_superchats import SuperchatArchiver
import argparse, asyncio, json
import pytchat
from multichannel_recording_base import MultichannelRecordingBase
from database.psql_db import PostgresDB

class comb_recorder(MultichannelRecordingBase):
    def __init__(self,exloop, api_pts_used = 0.0, keyfilepath = "yt_api_key.txt"):
        self.running = True
        config_files = {'yt_key': keyfilepath}
        super().__init__(exloop, 128, config_files, 1, api_pts_used, 10000, 100)
        self.setup_logging(f"record_comb")
        with open("postgres-config.json") as pgsql_config_file:
            self.pgsql_creds = json.load(pgsql_config_file)
        self.db = PostgresDB(username=self.pgsql_creds["username"], password=self.pgsql_creds["password"],
                             host=self.pgsql_creds["host"], database=self.pgsql_creds["database"])

    async def main(self):
        self.setup_sigusr_handlers(self.loop)
        asyncio.ensure_future(self.yt_api.reset_timer())
        old_streams = await self.db.get_all_unfinished_vids(12)
        for entry in old_streams:
            self.video_analysis.setdefault(entry,None)
            self.running_streams.append(entry)
        await self.log_output(self.video_analysis)
        for stream in list(self.video_analysis.keys()):
            self.video_analysis[stream] = SuperchatArchiver(stream,self.yt_api, file_suffix=".comb.txt",min_successful_attempts = 2,minutes_wait = 1,logger = self.logger, t_pool = self.t_pool)
            try:
                await self.video_analysis[stream].main()
            except pytchat.exceptions.InvalidVideoIdException:
                await self.log_output("aaa")
            self.analyzed_streams.append(stream)
            await self.yt_api.sleep_by_points(request_mode=False)


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
    loop = asyncio.get_event_loop()
    monitor = comb_recorder(loop, args.pts, keyfilepath)
    try:
        loop.run_until_complete(monitor.main())
    except asyncio.CancelledError:
        pass
