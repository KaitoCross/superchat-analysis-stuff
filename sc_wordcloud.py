import argparse, os, json
from wordcloud import WordCloud, STOPWORDS
import matplotlib.pyplot as plt
import os
import numpy as np
from PIL import Image
from pathlib import Path

class superchat_wordcloud:
    def __init__(self, log, mask_img_path = None, targetDir = "./", logname = "some", font = None):
        if type(log) is str:
            self.logpath = Path(log)
            self.sc_log_file = open(self.logpath, encoding='utf-8')
            self.sc_log = json.load(self.sc_log_file)
            self.logname = self.logpath.stem
        elif type(log) is list:
            self.sc_log = log
            self.logname = logname
        else:
            exit(-1)
        self.font = font
        self.stopwords_file = open("stopwords.txt","r")
        if mask_img_path:
            self.mask_img = Image.open(mask_img_path)
        else:
            self.mask_img = None
        self.target_dir = targetDir

    def generate(self):
        stopwords_from_file = self.stopwords_file.read()
        self.ignored_words = stopwords_from_file.split()
        self.stopwords_file.close()
        longstring = ""
        mask = np.array(self.mask_img)
        for superchat in self.sc_log:
            if superchat["message"]:
                if '_' not in superchat["message"]:
                    longstring += " "+superchat["message"]
        STOPWORDS.update(self.ignored_words)
        wordcloud = WordCloud(font_path = self.font, collocations=False, background_color="white",width=1280, height=720, mask = mask).generate(longstring)
        wordcloud.to_file(self.target_dir+self.logname+"-wordcloud.png")
        plt.axis("off")

if __name__ =='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('logpath', metavar='sc_file_path', type=str,
                        help='path to the superchat log file')
    parser.add_argument('maskimage', metavar='maskimage', type=str,
                        help='path to the image to be used as mask')
    parser.add_argument('--font', action='store', type=str, help='font path', default=None)
    args = parser.parse_args()
    scw = superchat_wordcloud(args.logpath,args.maskimage, font = args.font)
    scw.generate()