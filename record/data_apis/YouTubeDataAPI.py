from .VideoMetaAPIBase import VideoMetaAPIBase
from typing import Set
from aiohttp_requests import requests
import traceback


class YouTubeDataAPI(VideoMetaAPIBase):
    def __init__(self, api_key, chans, reset_tz, log_cb, pts_used = 0):
        super().__init__(api_key,chans,reset_tz,log_cb,pts_used)

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
        self.add_cost()
        if 'items' in planstreams_raw_json.keys():
            streams = {streams['id']['videoId'] for streams in planstreams_raw_json['items']}
        return streams

    async def get_live_streams_multichannel(self, channels) -> Set:
        res_set = set()
        try:
            for chan_id in channels:
                res_set = res_set.union(await self.get_live_streams(chan_id))
        except ValueError:
            self._points_used = 10000.0
            await self._log("API Quota exceeded!", 30)
        return res_set

    def points_depleted(self, add_points = 0):
        return self._points_used + add_points >= (self._points - self._desired_leftover_points)

    async def log_used(self, add_points = 0):
        await self._log(f'approx. {self._points_used+add_points} YouTube Data API points used')
