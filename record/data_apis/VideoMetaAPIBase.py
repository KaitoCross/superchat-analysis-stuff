import math, pytz, asyncio, copy
from datetime import datetime, timedelta, timezone

class VideoMetaAPIBase(object):
    def __init__(self, api_key, chans, reset_tz, log_callback):
        self._api_key = api_key
        self._points = 10000 #available API points
        self._points_used = 0
        self._desired_leftover_points = 100 #for safety measure since the SuperchatArchiver objects will use some API points
        self._cost_per_search_request = 100
        self._min_sleep = 300
        #self.sleep_dur = (60.0 * 60.0 * 24.0) / self.search_requests_left(chans)
        self._timezone = reset_tz #pytz.timezone('America/Los_Angeles')
        self._log = log_callback
        self.chan_nrs = chans

    @property
    def points_used(self):
        return self._points_used

    @property
    def points(self):
        return self._points

    @points.setter
    def points(self, a: int):
        self._points_used = a

    def set_api_key(self, key: str):
        self._api_key = key

    def search_requests_left(self):
        return math.floor((self._points - self._points_used) / (self.chan_nrs * self._cost_per_search_request))

    async def get_live_streams(self, channel_id: str):
        pass

    async def get_live_streams_multichannel(self, channels):
        pass

    def add_cost(self, cost = 0):
        if cost == 0:
            cost = self._cost_per_search_request
        self._points_used += cost

    def mark_all_used(self):
        self._points_used = copy.copy(self._points)

    def get_sleep_dur(self):
        temp = self.time_until_specified_hour(0, self._timezone)
        sleep_dur = max(temp.total_seconds() / self.search_requests_left(), self._min_sleep)
        return sleep_dur

    async def get_reset_sleep_dur(self):
        time_now = datetime.now(tz=self._timezone)
        resume_at = self.next_specified_hour_datetime(0, pytz.timezone('America/Los_Angeles'))
        t_delta = resume_at - time_now
        sleep_dur = t_delta.total_seconds()
        return sleep_dur, resume_at

    def points_depleted(self, add_points = 0):
        pass

    async def sleep_by_points(self, add_points = 0):
        # If we somehow used too many API points, calculate waiting time between now and midnight pacific time
        reset_used = False
        sleep_dur = None
        total_pts_used = self._points_used + add_points
        if self.points_depleted(add_points):
            sleep_dur, resume_at = await self.get_reset_sleep_dur()
            requests_left = 0
            reset_used = True
        else:
            # Calculate how long I have to wait for the next search request
            # trying not to exceed the 24h API usage limits while also accounting for time already passed since last
            # API point reset (which happens at midnight pacific time)
            requests_left = self.search_requests_left()
            if requests_left > 0:
                sleep_dur = self.get_sleep_dur()
                resume_at = datetime.now(tz=pytz.timezone('Europe/Berlin')) + timedelta(seconds=sleep_dur)
            else:
                sleep_dur, resume_at = await self.get_reset_sleep_dur()
                reset_used = True
        awake_at = resume_at.astimezone(pytz.timezone('Europe/Berlin'))
        await self.log_sleep(sleep_dur, total_pts_used, awake_at, requests_left)
        await asyncio.sleep(sleep_dur)
        if reset_used:
            await self.reset_pts()
        return reset_used, sleep_dur

    async def log_sleep(self, sleep_dur, total_points_used, awake_at, requests_left):
        await self._log(f'sleeping again for {sleep_dur / 60} minutes')
        await self._log(f'approx. {total_points_used} YouTube points used')
        await self._log(f"{requests_left} requests left")
        await self._log(f'next run at: {awake_at.isoformat()} Berlin Time')

    async def reset_pts(self):
        self._points_used = 0
        await self._log(f'used points reset at {datetime.now(tz=pytz.timezone('Europe/Berlin')).isoformat()} Berlin time')

    async def reset_timer(self, w_hour = 0):
        time_until_reset = self.time_until_specified_hour(w_hour,self._timezone)
        while True:
            await asyncio.sleep(time_until_reset.total_seconds())
            await self._log(f"midnight reset taking place")
            await self.reset_pts()
            await asyncio.sleep(1)
            time_until_reset = self.time_until_specified_hour(w_hour, self._timezone)

    def time_until_specified_hour(self, w_hour, tzinfo_p):
        time_now = datetime.now(tz=tzinfo_p)
        reset_at = self.next_specified_hour_datetime(w_hour, tzinfo_p)
        t_delta = reset_at - time_now
        return t_delta

    def next_specified_hour_datetime(self,w_hour,tzinfo_p):
        time_now = datetime.now(tz=tzinfo_p)
        if time_now.hour >= w_hour:
            next_day = self.add_day(time_now)
            new_time = next_day.replace(hour=w_hour, minute=0, second=0, microsecond=0)
        else:
            new_time = time_now.replace(hour=w_hour,minute=0, second=0, microsecond=0)
        return new_time

    @staticmethod
    def add_day(today):
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