import logging, logging.handlers, concurrent.futures, pytz, signal, asyncio
from pytchat import config
from data_apis.YouTubeCustomAPI import YouTubeCustomAPI

class MultichannelRecordingBase(object):
    def __init__(self, exloop, tpoolworkers, config_files: dict,
                 watched_chans, pts_used, pts_avail = 10000, desired_pts_left = 100):
        self.running = True
        self.t_pool = concurrent.futures.ThreadPoolExecutor(max_workers=tpoolworkers)
        self.loop = exloop
        self.reset_tz = pytz.timezone('America/Los_Angeles')
        self.yt_api_key = "####"
        self.video_analysis = {}
        self.running_streams = []
        self.analyzed_streams = []
        self.config_files = config_files
        self.load_config()
        self.yt_api = YouTubeCustomAPI(self.yt_api_key, watched_chans, self.reset_tz,
                         self.log_output, pts_used=pts_used, pts_avail=pts_avail, desired_pts_left=desired_pts_left)

    def load_config(self):
        with open(self.config_files['yt_key'], "r") as keyfile:
            self.yt_api_key = keyfile.read()
        holo_keyfile = self.config_files.get("holodex","")
        if holo_keyfile:
            with open(holo_keyfile,"r") as keyfile:
                self.holo_api_key = keyfile.read().replace("\n", "")

    def setup_sigusr_handlers(self, aloop):
        aloop.add_signal_handler(signal.SIGUSR1,
                                lambda signame="SIGUSR1": asyncio.create_task(self.signal_handler_1(signame)))
        aloop.add_signal_handler(signal.SIGUSR2,
                                lambda signame="SIGUSR2": asyncio.create_task(self.signal_handler_2(signame)))

    def setup_logging(self, app_name):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        fh = logging.handlers.TimedRotatingFileHandler(f"logs/{app_name}.debuglog", when='midnight', utc=True, backupCount=183)
        fh.setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        dbg_formatter = config.mylogger.MyFormatter()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(dbg_formatter)
        ch.setFormatter(formatter)
        self.logger.addHandler(fh)
        self.logger.addHandler(ch)

    async def log_output(self, logmsg, level = 20):
        msg_string = ""
        msg_len = len(logmsg)
        if isinstance(logmsg, tuple):
            part_count = 0
            for msg_part in logmsg:
                part_count += 1
                msg_string += str(msg_part)
                if msg_len > part_count:
                    msg_string += " "
        elif isinstance(logmsg, str):
            msg_string = logmsg
        else:
            msg_string = str(logmsg)
        await self.loop.run_in_executor(self.t_pool,self.logger.log,level,msg_string)

    async def signal_handler_1(self, sig):
        for stream in self.video_analysis:
            if self.video_analysis[stream]:
                self.video_analysis[stream].cancel()
        # self.running = False
        await self.log_output("cancelled logging")
        pts_used = await self.yt_api.get_pts_used()
        await self.log_output(f"youtube api points used: {pts_used}")

    async def signal_handler_2(self, sig):
        for stream in self.video_analysis:
            if self.video_analysis[stream]:
                await self.log_output(str(self.video_analysis[stream]))