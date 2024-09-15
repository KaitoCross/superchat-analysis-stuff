#!/usr/bin/env python3
import argparse, os, json, many_stop_words, collections, six, psycopg2
from wordcloud import WordCloud, STOPWORDS
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from pathlib import Path
from mecabwrap import do_mecab

class superchat_wordcloud:
    def __init__(self, video_id, mask_img_path = None, targetDir = "./", font=None, logname = "unnamed"):
        self.font = font
        self.video_id = video_id
        self.stopwords_file = open("stopwords.txt","r")
        if mask_img_path and mask_img_path != "None":
            self.mask_img = Image.open(mask_img_path)
        else:
            self.mask_img = None
        self.target_dir = targetDir
        self.pgsql_config_file = open("postgres-config-qt.json")
        self.pgsql_creds = json.load(self.pgsql_config_file)
        
    def iterable(self,arg):
        return (isinstance(arg, collections.Iterable) and not isinstance(arg, six.string_types))

    def generate(self):
        conn = psycopg2.connect(dbname=self.pgsql_creds["database"], user=self.pgsql_creds["username"], host = self.pgsql_creds["host"], password = self.pgsql_creds["password"])
        cur = conn.cursor()
        cur.execute("SELECT message_txt FROM messages WHERE video_id = %s AND NOT currency = %s;",(self.video_id,"MGI"))
        results = cur.fetchall()
        conn.close()
        self.ignored_words=set()
        stopwords_from_file = self.stopwords_file.read()
        for word in stopwords_from_file.split():
            self.ignored_words.add(word)
        self.stopwords_file.close()
        self.ignored_words = set.union(many_stop_words.get_stop_words("ja"),self.ignored_words)
        longstring = ""
        if self.mask_img:
            mask = np.array(self.mask_img)
        else:
            mask = None
        amount_scs = 0
        for superchat in results:
            if superchat[0]:
                amount_scs += 1
                if '_' not in superchat[0]:
                    mecabbed = do_mecab(superchat[0], '-Owakati')
                    longstring += " "+mecabbed
        print("generating wordcloud from %d messages", amount_scs)
        STOPWORDS.update(self.ignored_words)
        wordcloud = WordCloud(font_path = self.font, collocations=False, background_color="white",width=1280, height=720, mask = mask).generate(longstring)
        dest_image = self.target_dir+self.video_id+"-wordcloud.png"
        wordcloud.to_file(dest_image)
        

if __name__ =='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('vidID', metavar='sc_file_path', type=str,
                        help='youtube video ID')
    parser.add_argument('maskimage', metavar='maskimage', type=str,
                        help='path to the image to be used as mask')
    parser.add_argument('--font',action='store', type=str, help='font path', default=None)
    args = parser.parse_args()
    scw = superchat_wordcloud(args.vidID, args.maskimage, font = args.font)
    scw.generate()
