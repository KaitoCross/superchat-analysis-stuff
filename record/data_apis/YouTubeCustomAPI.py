from .VideoMetaAPIBase import VideoMetaAPIBase
from typing import Set
from aiohttp_requests import requests
from youtube_api import YouTubeDataAPI
from datetime import datetime
from functools import partial
import traceback, isodate


class YouTubeCustomAPI(VideoMetaAPIBase):
    def __init__(self, api_key, chans, reset_tz, log_cb, pts_used = 0, pts_avail = None, desired_pts_left = None):
        super().__init__(api_key,chans,reset_tz,log_cb,pts_used)
        self._ext_api = YouTubeDataAPI(api_key)
        self._points_used += 1 #uses 1p to check key validity
        if pts_avail is not None:
            self._points = pts_avail
        if desired_pts_left is not None:
            self._desired_leftover_points = desired_pts_left

    async def get_live_streams(self, channel_id: str) -> Set:
        # catch only planned streams. Caution! API returns recently finished streams as "upcoming" too!
        streams = set()
        try:
            planstreams_search = await requests.get(
                f'https://youtube.googleapis.com/youtube/v3/search?part=id&channelId={channel_id}&eventType=upcoming&type=video&key={self._api_key}')
            planstreams_raw_json = await planstreams_search.json()
        except Exception as e:
            self._log(e, 40)
            self._log(traceback.format_exc(), 40)
        if "error" in planstreams_raw_json.keys():
            if planstreams_raw_json['error']['code'] == 403:
                raise ValueError("API Quota exceeded!")
        await self.add_cost()
        if 'items' in planstreams_raw_json.keys():
            streams = {streams['id']['videoId'] for streams in planstreams_raw_json['items']}
        return streams

    async def get_live_streams_multichannel(self, channels) -> Set:
        res_set = set()
        try:
            for chan_id in channels:
                res_set = res_set.union(await self.get_live_streams(chan_id))
        except ValueError:
            async with self._lock:
                self._points_used = 10000.0
            await self._log("API Quota exceeded!", 30)
        return res_set

    async def points_depleted(self, add_points = 0):
        total_pts_used = await self.get_pts_used() + add_points
        return total_pts_used >= (self._points - self._desired_leftover_points)

    async def log_used(self, add_points = 0):
        total_pts_used = await self.get_pts_used() + add_points
        await self._log(f'approx. {total_pts_used} YouTube Data API points used')

    def get_video_info(self, video_id: str):
        response = None
        try:
            response = self._ext_api.get_video_metadata(video_id=video_id, parser=None,
                                                   part=["liveStreamingDetails", "contentDetails", "snippet"])
            api_metadata = {"channel": response["snippet"]["channelTitle"],
                            "channel_id": response["snippet"]["channelId"],
                            "video_id": video_id,
                            "title": response["snippet"]["title"],
                            "live": response["snippet"]["liveBroadcastContent"],
                            "caught_while": response["snippet"]["liveBroadcastContent"],
                            "publishDateTime": datetime.strptime(response["snippet"]["publishedAt"] + " +0000",
                                                                 "%Y-%m-%dT%H:%M:%SZ %z").timestamp()}
            delta = isodate.parse_duration(response["contentDetails"]["duration"])
            api_metadata["length"] = delta.total_seconds()
            if 'liveStreamingDetails' in response.keys():
                api_metadata["liveStreamingDetails"] = {}
                for d in response["liveStreamingDetails"].keys():
                    if "Time" in d or "time" in d:
                        api_metadata["liveStreamingDetails"][d] = datetime.strptime(
                            f'{response["liveStreamingDetails"][d]} +0000', "%Y-%m-%dT%H:%M:%SZ %z").timestamp()
            return api_metadata

        except Exception as e:
            print(video_id)
            print(e)
            print(response)
            return None

    async def async_get_video_info(self, video_id: str, loop, t_pool):
        api_metadata = await loop.run_in_executor(t_pool,self.get_video_info,video_id)
        await self.add_cost(1)
        return api_metadata

    async def async_get_channel_metadata(self, channel_id: str, loop, t_pool):
        api_metadata = await loop.run_in_executor(t_pool,partial(self._ext_api.get_channel_metadata,channel_id,None,
                                                                 part=["snippet","contentDetails"]))
        await self.add_cost(1)
        return api_metadata

    async def async_get_videos_from_playlist_id(self, playlist_id, loop, t_pool):
        api_metadata = await loop.run_in_executor(t_pool, partial(self._ext_api.get_videos_from_playlist_id, playlist_id, None,
                                                  part=["snippet","contentDetails"]))
        await self.add_cost(1)
        return api_metadata