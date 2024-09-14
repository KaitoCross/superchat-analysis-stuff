
class StorageInterface(object):
    def __init__(self):
        self._dataqueue = list()

    async def update_metadata(self, video_id, channel_id, title, caught_while, live,
                        retries_of_rerecording,
                        retries_of_rerecording_had_scs, length = None, endedLogAt = None, publishDateTime = None, scheduledStartTime = None,
                        actualStartTime= None, actualEndTime = None, old_title = None, membership = None):
        pass

    async def get_video_metadata(self, video_id: str):
        pass

    async def insert_video_metadata(self, video_id, channel_id, title, startedlogat, createddatetime):
        pass

    async def insert_channel_metadata(self, channel_id: str, name: str, tracked = False):
        pass

    async def insert_message(self, video_id, chat_id, user_id, message_txt, time_sent, currency, value, color):
        pass

    async def insert_chan_name_hist(self, channel_id, name, time_discovered, time_used):
        pass

    async def get_size(self, video_id: str) -> int:
        pass

    async def log_exists(self, video_id: str) -> bool:
        pass

    async def get_retries(self, video_id: str) -> tuple[int,int]:
        pass

    async def flush(self):
        pass