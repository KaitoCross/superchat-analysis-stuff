from .storage_interface import StorageInterface
import pathlib as pl, json

class JSONLogDB(StorageInterface):
    def __init__(self, video_id: str, channel_id: str, suffix: str = ""):
        super().__init__()
        self._video_id = video_id
        self._channel_id = channel_id
        self._path_prefix = pl.Path(f"txtarchive/{self._channel_id}")
        self._msg_log_file = self._path_prefix / "sc_logs" / f"{self._video_id}.json{suffix}"
        self._donor_file = self._path_prefix / "vid_stats" / "donors" / f"{self._video_id}.json{suffix}"
        self._stats_file = self._path_prefix / "vid_stats" / f"{self._video_id}_stats.json{suffix}"
        self._metadata_list = list()
        self._stats_list = list()
        self._msgs = dict()
        self._donors = dict()

    @property
    def msgs(self):
        return self._msgs

    def connect(self):
        self._msg_log_file.parent.mkdir(parents=True, exist_ok=True)
        self._donor_file.parent.mkdir(parents=True, exist_ok=True)

    async def log_exists(self, video_id: str) -> bool:
        return self._msg_log_file.exists()

    async def get_size(self, video_id: str) -> int:
        return self._msg_log_file.stat().st_size if await self.log_exists(video_id) else -1

    async def add_video_metadata(self, meta: dict):
        self._metadata_list.append(meta)

    async def add_stats(self,stats):
        self._stats_list.append(stats)

    async def insert_message(self, video_id, chat_id, user_id, message_txt, time_sent, currency, value, color, **kwargs):
        sc_info = {"id": chat_id, "type": kwargs.get("msg_type","None"), "time": time_sent.isoformat(), "currency": currency, "value": value,
                   "user_id": user_id, "message": message_txt, "color": color}
        member_level = kwargs.get("member_level","")
        if member_level:
            sc_info["member_level"] = member_level
        self._msgs.setdefault(chat_id, sc_info)

    async def insert_new_mem_msg(self, chat_id, msg_type, time, user_id, member_level):
        msg_info = {"id": chat_id, "type": msg_type, "time": time.isoformat(), "user_id": user_id, "member_level": member_level}
        self._msgs.setdefault(chat_id, msg_info)

    async def add_donors(self, user_id, name):
        self._donors.setdefault(user_id,{"names": {name}, "donations": {}})
        self._donors[user_id]["names"].add(name)

    async def flush(self):
        proper_msg_list = list(self._msgs.values())
        unique_donors = {}
        unique_currency_donors = {}
        count_dono = 0
        for c_id, msg in self._msgs.items():
            if msg["type"] not in ["newSponsor", "sponsorMessage", "giftRedemption"]:
                count_dono += 1
                self._donors.setdefault(msg["user_id"], {})
                donations = self._donors[msg["user_id"]]["donations"].setdefault(msg["currency"], [0, 0])
                self._donors[msg["user_id"]]["donations"][msg["currency"]][0] = donations[0] + 1  # amount of donations
                self._donors[msg["user_id"]]["donations"][msg["currency"]][1] = donations[1] + msg["value"]  # total amount of money donated
                unique_donors.setdefault(msg["currency"], set())
                unique_donors[msg["currency"]].add(msg["user_id"])
        for currency in unique_donors.keys():
            unique_currency_donors[currency] = len(unique_donors[currency])
        for uid in self._donors.keys():
            if "names" in self._donors[uid].keys():
                self._donors[uid]["names"] = list(self._donors[uid]["names"])
        with open(self._msg_log_file, "w") as f:
            f.write(json.dumps(proper_msg_list))
        with open(self._stats_file, "w") as f_stats:
            f_stats.write(json.dumps([self._metadata_list[-1], self._stats_list[-1], unique_currency_donors]))
        with open(self._donor_file, "w") as f_donors:
            f_donors.write(json.dumps(self._donors))
        return len(proper_msg_list), count_dono

    async def cancel(self):
        self._msg_log_file.rename(f"{self._msg_log_file}.cancelled")
        self._donor_file.rename(f"{self._donor_file}.cancelled")
        self._stats_file.rename(f"{self._stats_file}.cancelled")

    def clear_stats(self):
        self._stats_list.clear()