from typing import Tuple
import asyncpg, asyncio
from datetime import datetime, timezone, timedelta
from .storage_interface import StorageInterface

class PostgresDB(StorageInterface):
    def __init__(self, username, password, host, database):
        super().__init__()
        self._username = username
        self._password = password
        self._dbhost = host
        self._database = database
        self._msgqueue = list()
        self._channamequeue = list()
        self._chanqueue = list()
        self._data_event = asyncio.Event()
        self.running = True

    async def connect(self, prep=False):
        self._conn = await asyncpg.connect(user = self._username, password = self._password,
                                           host = self._dbhost, database = self._database)
        if prep:
            self._insert_channel_sql = await self._conn.prepare("INSERT INTO channel(id, name, tracked) VALUES ($1,$2,$3) "
                                                                "ON CONFLICT DO NOTHING")
            self._channel_name_history_sql = await self._conn.prepare(
                "INSERT INTO chan_names(id, name, time_discovered, time_used) "
                "VALUES ($1,$2,$3,$4) ON CONFLICT (id,name) DO UPDATE SET time_used = $4")
            self._insert_message_sql = await self._conn.prepare("INSERT INTO messages(video_id, chat_id, user_id, message_txt, "
                                                                "time_sent, currency, value, color) "
                                                                "VALUES ($1,$2,$3,$4,$5,$6,$7,$8) ON CONFLICT DO NOTHING")
        return

    async def disconnect(self):
        if not self._conn.is_closed():
            await self._conn.close()

    async def update_metadata(self, video_id, channel_id, title, caught_while, live,
                        retries_of_rerecording,
                        retries_of_rerecording_had_scs, length = None, endedLogAt = None, publishDateTime = None, scheduledStartTime = None,
                        actualStartTime = None, actualEndTime = None, old_title = None, membership = None, **kwargs):
        sql = "UPDATE video SET caught_while = $2, live = $3, title = $4, "\
              "retries_of_rerecording = $5, retries_of_rerecording_had_scs = $6 WHERE video_id = $1"
        self._dataqueue.append((sql,(video_id, caught_while, live, title,
                                    retries_of_rerecording,retries_of_rerecording_had_scs)))
        if scheduledStartTime is not None:
            self._dataqueue.append(("UPDATE video SET scheduledstarttime = $2 WHERE video_id = $1",
                                    (video_id, datetime.fromtimestamp(scheduledStartTime, timezone.utc))))
        if actualStartTime is not None:
            self._dataqueue.append(("UPDATE video SET actualstarttime = $2 WHERE video_id = $1",
                                    (video_id, datetime.fromtimestamp(actualStartTime, timezone.utc))))
        if actualEndTime is not None:
            self._dataqueue.append(("UPDATE video SET actualendtime = $2 WHERE video_id = $1",
                                    (video_id, datetime.fromtimestamp(actualEndTime, timezone.utc))))
        if old_title is not None:
            self._dataqueue.append(("UPDATE video SET old_title = $2 WHERE video_id = $1",
                                    (video_id, old_title)))
        if length is not None:
            self._dataqueue.append(("UPDATE video SET length = $2 WHERE  video_id = $1",
                                    (video_id, length)))
        if publishDateTime is not None:
            self._dataqueue.append(("UPDATE video SET publishDateTime = $2 WHERE video_id = $1",
                                    (video_id, datetime.fromtimestamp(publishDateTime, timezone.utc))))
        if endedLogAt is not None:
            self._dataqueue.append(("UPDATE video SET endedLogAt = $2 WHERE video_id = $1",
                                    (video_id, datetime.fromtimestamp(endedLogAt,timezone.utc))))
        if membership is not None:
            self._dataqueue.append(("UPDATE video SET membership = $2 WHERE video_id = $1",
                                    (video_id, membership)))
        self.trigger()
        #await self.flush()
        return

    async def get_video_metadata(self, video_id: str):
        await self.connect()
        meta_row = await self._conn.fetchrow('SELECT c.name, channel_id, title, caught_while, live, old_title, length, createdDateTime, publishDateTime, startedLogAt, endedLogAt, scheduledStartTime, actualStartTime, actualEndTime, retries_of_rerecording, retries_of_rerecording_had_scs, membership FROM video INNER JOIN channel c on channel_id = c.id WHERE video_id = $1', video_id)
        await self.disconnect()
        res = dict(meta_row) if meta_row else dict()
        return res

    async def insert_video_metadata(self, video_id, channel_id, title, startedlogat, createddatetime):
        sql = "INSERT INTO video (video_id,channel_id,title,startedlogat,createddatetime) "\
              "VALUES($1,$2,$3,$4,$5) ON CONFLICT DO NOTHING"
        self._dataqueue.append((sql, (video_id, channel_id, title, startedlogat, createddatetime)))
        self._data_event.set()

    async def insert_channel_metadata(self, channel_id: str, name: str, tracked = False):
        sql = "INSERT INTO channel(id, name, tracked) VALUES ($1,$2,$3) ON CONFLICT "
        if tracked:
            sql += "(id) DO UPDATE SET tracked = $3"
            self._dataqueue.append((sql, (channel_id, name, tracked)))
        else:
            sql += "DO NOTHING"
            self._chanqueue.append((channel_id, name, tracked))
        #self._data_event.set()

    async def insert_message(self, video_id, chat_id, user_id, message_txt, time_sent, currency, value, color, **kwargs):
        sql = ("INSERT INTO messages(video_id, chat_id, user_id, message_txt, time_sent, currency, value, color) "
               "VALUES ($1,$2,$3,$4,$5,$6,$7,$8) ON CONFLICT DO NOTHING")
        self._msgqueue.append((video_id, chat_id, user_id, message_txt, time_sent, currency, value, color))

    async def insert_chan_name_hist(self, channel_id, name, time_discovered, time_used):
        sql = ("INSERT INTO chan_names(id, name, time_discovered, time_used) "
               "VALUES ($1,$2,$3,$4) ON CONFLICT (id,name) DO UPDATE SET time_used = $4")
        self._channamequeue.append((channel_id, name, time_discovered, time_used))
        #self._data_event.set()

    async def get_size(self, video_id: str) -> int:
        pass

    async def log_exists(self, video_id: str) -> bool:
        pass

    async def get_retries(self, video_id: str) -> Tuple[int,int]:
        await self.connect()
        row = await self._conn.fetchrow('SELECT retries_of_rerecording_had_scs, retries_of_rerecording '
                                        'FROM video WHERE video_id = $1', video_id)
        await self.disconnect()
        successful_sc_recordings = 0
        repeats = 0
        if row:
            successful_sc_recordings = row["retries_of_rerecording_had_scs"] if row[
                "retries_of_rerecording_had_scs"] else 0
            repeats = row["retries_of_rerecording"] if row["retries_of_rerecording"] else 0
        return successful_sc_recordings, repeats

    async def get_recorded_vid_ids(self, channel_id, last_hours = 12):
        await self.connect()
        query = "select video_id from video where retries_of_rerecording_had_scs = 2 and caught_while <> 'none' "\
                "and scheduledstarttime < $1 and channel_id = $2 order by scheduledstarttime desc"
        old_streams = await self._conn.fetch(query, datetime.now(timezone.utc) - timedelta(hours=last_hours), channel_id)
        await self.disconnect()
        recorded_set = set([rec["video_id"] for rec in old_streams])
        return recorded_set

    async def get_all_unfinished_vids(self, last_hours = 12):
        await self.connect()
        query = ("select video_id from video where (retries_of_rerecording_had_scs < 2 or retries_of_rerecording_had_scs is null) "
                 "and caught_while <> 'none' and scheduledstarttime < $1 order by scheduledstarttime")
        old_streams = await self._conn.fetch(query, datetime.now(timezone.utc) - timedelta(hours=last_hours))
        await self.disconnect()
        recorded_set = set([rec["video_id"] for rec in old_streams])
        return recorded_set

    async def flush(self):
        await self.connect(True)
        async with self._conn.transaction():
            for rawdata in self._dataqueue:
                sql, values = rawdata
                await self._conn.execute(sql, *values)
        self._dataqueue.clear()
        async with self._conn.transaction():
            await self._insert_channel_sql.executemany(self._chanqueue)
            self._chanqueue.clear()
        async with self._conn.transaction():
            await self._channel_name_history_sql.executemany(self._channamequeue)
            self._channamequeue.clear()
        async with self._conn.transaction():
            await self._insert_message_sql.executemany(self._msgqueue)
            self._msgqueue.clear()
        await self.disconnect()

    async def flush_on_event(self):
        while self.running:
            await self._data_event.wait()
            await self.flush()
            self._data_event.clear()

    def trigger(self):
        self._data_event.set()