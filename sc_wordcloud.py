import argparse, os, json
from wordcloud import WordCloud, STOPWORDS
import matplotlib.pyplot as plt
import os
import numpy as np
from PIL import Image

parser = argparse.ArgumentParser()
parser.add_argument('logpath', metavar='sc_file_path', type=str,
                    help='path to the superchat log file')
parser.add_argument('maskimage', metavar='maskimage', type=str,
                    help='path to the image to be used as mask')
args = parser.parse_args()

sc_log_file = open(args.logpath, encoding='utf-8')

sc_log = json.load(sc_log_file)

stopwords_file = open("stopwords.txt","r")
stopwords_from_file = stopwords_file.read()
ignored_words = stopwords_from_file.split()
stopwords_file.close()
longstring = ""

mask = np.array(Image.open(args.maskimage))

for superchat in sc_log:
    if superchat["message"]:
        if '_' not in superchat["message"]:
            longstring += " "+superchat["message"]
STOPWORDS.update(ignored_words)
wordcloud = WordCloud(collocations=False, background_color="white",width=1280, height=720, mask = mask).generate(longstring)
#print(wordcloud.words_)
filename=args.logpath.split(".")[0]
wordcloud.to_file(filename+"-wordcloud.png")
plt.imshow(wordcloud, interpolation="bilinear")
plt.axis("off")
plt.show()