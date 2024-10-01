import asyncio, pytz, argparse, time, os, functools, json, isodate, pathlib, concurrent.futures, os, psycopg2, psycopg2.extras
from datetime import datetime, timezone, timedelta

class SuperchatLog(object):

    def __init__(self,statfile,logfile):
        self.statf = open(statfile)
        self.logf = open(logfile)
        self.donorf = None
        self.log = json.load(self.logf)
        self.stats = json.load(self.statf)
        infos = self.stats[0]
        self.infos = infos
        self.channelName = infos["channel"]
        self.channelId = infos["channel_id"]
        self.videoid = infos["video_id"]
        self.videotitle = infos["title"]
        self.filters = ["giftRedemption", "newSponsor", "sponsorMessage"]
        self.published = datetime.fromtimestamp(infos["publishDateTime"],timezone.utc)
        self.len = infos["length"]
        self.liveStreamingDetails = {}
        for t_info in infos["liveStreamingDetails"].keys():
            self.liveStreamingDetails[t_info] = datetime.fromtimestamp(infos["liveStreamingDetails"][t_info],timezone.utc)
        self.donor_seperate = "user" not in self.log[0].keys()
        if self.donor_seperate:
            donorfile = pathlib.Path(logfile).parent / ".." / "vid_stats" / "donors" / os.path.basename(self.logf.name)
            self.donorf = open(donorfile.resolve())
            self.donors = json.load(self.donorf)

    def chatlog(self):
        loglist = list()
        for entry in self.log:
            if entry["type"] not in self.filters:
                logmsg = (self.videoid,entry.get("id","RIP"),entry["user_id"],entry["message"],datetime.fromisoformat(entry["time"]),
                                entry["currency"],entry["value"],entry.setdefault("color",0))
                loglist.append(logmsg)
        return loglist

    def usernamelog(self):
        loglist = list()
        userlist = list()
        for entry in self.log:
            if self.donor_seperate and entry["type"] not in self.filters:
                logmsg = (entry["user_id"], self.donors[entry["user_id"]]["names"][0],
                          datetime.fromisoformat(entry["time"]))
                loglist.append(logmsg)
                userlist.append((entry["user_id"], self.donors[entry["user_id"]]["names"][0], False))
            elif "user" in entry.keys():
                logmsg = (entry["user_id"], entry["user"],
                          datetime.fromisoformat(entry["time"]))
                loglist.append(logmsg)
                userlist.append((entry["user_id"], entry["user"], False))
        return loglist, userlist

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('basepath', metavar='N', type=str,
                        help='superchat log', default='')
    args = parser.parse_args()
    pgsql_config_file = open("postgres-config.json")
    pgsql_creds = json.load(pgsql_config_file)
    conn = psycopg2.connect("dbname="+pgsql_creds["database"]+" user="+pgsql_creds["username"])
    p = pathlib.Path(args.basepath)
    cur = conn.cursor()
    folders = [x for x in p.iterdir() if x.is_dir() and "UC" in x.parts[-1]]
    for channel in folders:
        statfolder = channel / "vid_stats"
        print(channel)
        statfiles = [x for x in statfolder.iterdir() if x.is_file() and ".json" in x.parts[-1]]
        for s_file in statfiles:
            l_f_name = s_file.parts[-1].replace("_stats","")
            lf_path = channel / "sc_logs" / l_f_name
            if lf_path.is_file():
                if lf_path.stat().st_size > 2:
                    a = SuperchatLog(s_file, lf_path)
                    cur.execute("INSERT INTO channel VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",(a.channelId,a.channelName,True))
                    cur.execute(
                        "INSERT INTO video (live, createddatetime, title, video_id, channel_id) "
                        "VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                        (a.infos["live"], a.published, a.videotitle, a.videoid,a.channelId))
                    if "scheduledStartTime" in a.liveStreamingDetails.keys():
                        cur.execute("UPDATE video SET scheduledstarttime = %s WHERE video_id = %s",
                                    (a.liveStreamingDetails["scheduledStartTime"],a.videoid))
                    if "actualStartTime" in a.liveStreamingDetails.keys():
                        cur.execute("UPDATE video SET actualstarttime = %s WHERE video_id = %s",
                                    (a.liveStreamingDetails["actualStartTime"],a.videoid))
                    if "actualEndTime" in a.liveStreamingDetails.keys():
                        cur.execute("UPDATE video SET actualendtime = %s WHERE video_id = %s",
                                    (a.liveStreamingDetails["actualEndTime"],a.videoid))
                    if "old_title" in a.infos.keys():
                        cur.execute("UPDATE video SET old_title = %s WHERE  video_id = %s", (a.infos["old_title"],a.videoid))
                    if "length" in a.infos.keys():
                        cur.execute("UPDATE video SET length = %s WHERE  video_id = %s", (a.len,a.videoid))
                    if "caught_while" in a.infos.keys():
                        cur.execute("UPDATE video SET caught_while = %s WHERE  video_id = %s", (a.infos["caught_while"],a.videoid))
                    if "createdDateTime" in a.infos.keys():
                        cur.execute("UPDATE video SET createddatetime = %s WHERE video_id = %s",
                                    (datetime.fromtimestamp(a.infos["createdDateTime"], timezone.utc),a.videoid))
                    userlog, userlist = a.usernamelog()
                    psycopg2.extras.execute_batch(cur, "INSERT INTO channel VALUES (%s, %s, %s) ON CONFLICT DO NOTHING", tuple(userlist))
                    psycopg2.extras.execute_batch(cur, "INSERT INTO chan_names VALUES (%s, %s, %s) ON CONFLICT DO NOTHING", tuple(userlog))
                    clog = a.chatlog()
                    psycopg2.extras.execute_batch(cur, "INSERT INTO messages VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING", tuple(clog))

    conn.commit()
    cur.close()
    conn.close()