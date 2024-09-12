from .VideoMetaAPIBase import VideoMetaAPIBase
from typing import Set
import traceback, math, requests, aiohttp


class HolodexDataAPI(VideoMetaAPIBase):
    def __init__(self, api_key, chans, reset_tz, log_cb, pts_used = 0):
        super().__init__(api_key,chans,reset_tz,log_cb,pts_used)
        self.api_endpoint = "https://holodex.net/api/v2/users/live"
        self._cost_per_search_request = 10.0
        self._points = (24 * 60 / 10) * self._cost_per_search_request

    async def get_live_streams(self, channel_id: str) -> Set:
        pass

    async def get_live_streams_multichannel(self, channels) -> Set:
        res_set = set()
        try:
            async with aiohttp.ClientSession(headers={"X-APIKEY": self._api_key}) as session:
                apiparams = {"channels": ",".join(channels)}
                async with session.get(self.api_endpoint, params=apiparams) as resp:
                    self.add_cost()
                    if resp.status == 200:
                        streams_raw_json = await resp.json()
                        for streams in streams_raw_json:
                            if "membersonly" not in streams.get("topic_id", []):
                                res_set.add(streams['id'])
        except ValueError as v:
            await self._log("API Problem!", 30)
            await self._log(str(v), 30)
        except Exception as e:
            await self._log("live stream lookup failed!", 30)
            await self._log(str(e), 30)
        return res_set

    def points_depleted(self, add_points = 0):
        return self._points_used + add_points >= self._points

    async def log_used(self, add_points = 0):
        await self._log(f'approx. {self._points_used} Holodex API points used')

    def search_requests_left(self):
        return math.floor((self._points - self._points_used) / self._cost_per_search_request)
