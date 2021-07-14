import argparse, os, json, many_stop_words, collections, six
from wordcloud import WordCloud, STOPWORDS
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from pathlib import Path
from mecabwrap import do_mecab

class superchat_wordcloud:
    def __init__(self, logpath, mask_img_path = None, targetDir = "./", font=None, logname = "unnamed"):
        if isinstance(logpath, six.string_types):
            self.logpath = Path(logpath)
            self.sc_log_file = open(self.logpath, encoding='utf-8')
            self.sc_log = json.load(self.sc_log_file)
        elif self.iterable(logpath):
            self.sc_log = logpath
            self.logpath = logname
        else:
            self.sc_log = []
        self.font = font
        self.stopwords_file = open("stopwords.txt","r")
        if mask_img_path and mask_img_path != "None":
            self.mask_img = Image.open(mask_img_path)
        else:
            self.mask_img = None
        self.target_dir = targetDir
        
    def iterable(self,arg):
        return (isinstance(arg, collections.Iterable) and not isinstance(arg, six.string_types))

    def generate(self):
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
        for superchat in self.sc_log:
            if superchat["message"]:
                amount_scs += 1
                if '_' not in superchat["message"]:
                    mecabbed = do_mecab(superchat["message"], '-Owakati')
                    longstring += " "+mecabbed
        print("generating wordcloud from %d messages", amount_scs)
        STOPWORDS.update(self.ignored_words)
        wordcloud = WordCloud(font_path = self.font, collocations=False, background_color="white",width=1280, height=720, mask = mask).generate(longstring)
        if isinstance(self.logpath,Path):
            dest_image = self.target_dir+self.logpath.stem+"-wordcloud.png"
        else: 
            dest_image = self.target_dir+self.logpath+"-wordcloud.png"
        wordcloud.to_file(dest_image)
        

if __name__ =='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('logpath', metavar='sc_file_path', type=str,
                        help='path to the superchat log file')
    parser.add_argument('maskimage', metavar='maskimage', type=str,
                        help='path to the image to be used as mask')
    parser.add_argument('--font',action='store', type=str, help='font path', default=None)
    args = parser.parse_args()
    scw = superchat_wordcloud(args.logpath, args.maskimage, font = args.font)
    scw.generate()
