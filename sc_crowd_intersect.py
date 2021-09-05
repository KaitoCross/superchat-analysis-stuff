import argparse, os, collections, six, psycopg2, json, datetime
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import upsetplot as up
from PIL import Image

class superchat_crowd:
    def __init__(self, channel_ids, mask_img_path = None, targetDir = "./", font=None, logname = "unnamed"):
        self.font = font
        self.channel_ids = channel_ids
        self.target_dir = targetDir
        self.pgsql_config_file = open("postgres-config-qt.json")
        self.pgsql_creds = json.load(self.pgsql_config_file)
        
    def iterable(self,arg):
        return (isinstance(arg, collections.Iterable) and not isinstance(arg, six.string_types))

    def generate(self):
        self.crowds = dict()
        conn = psycopg2.connect(dbname=self.pgsql_creds["database"], user=self.pgsql_creds["username"], host = self.pgsql_creds["host"], password = self.pgsql_creds["password"])
        cur = conn.cursor()
        cutoff_datetime = datetime.datetime(2021,8,1,tzinfo = datetime.timezone.utc)
        for channel in self.channel_ids:
            cur.execute("select name from channel where id = %s;",(channel,))
            chan_name = cur.fetchone()[0].replace(" Ch. hololive-EN","")
            chan_name = chan_name.replace("【NIJISANJI EN】","")
            print(chan_name)
            cur.execute("select distinct user_id from messages m inner join video v on m.video_id = v.video_id inner join channel c on c.id = v.channel_id where v.channel_id = %s and m.time_sent >= %s;",(channel,cutoff_datetime))
            results = cur.fetchall()
            self.crowds[chan_name] = set(results)
        conn.close()
        data = up.from_contents(self.crowds)
        updata = up.UpSet(data)
        updata.plot()
        plt.show()

if __name__ =='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('channel_ids', metavar='sc_file_path', type=str, nargs='+',
                        help='youtube video ID')
    parser.add_argument('--font',action='store', type=str, help='font path', default=None)
    args = parser.parse_args()
    scc = superchat_crowd(args.channel_ids, font = args.font)
    scc.generate()
