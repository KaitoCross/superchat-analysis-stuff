import argparse, os, json
from wordcloud import WordCloud, STOPWORDS
import matplotlib.pyplot as plt
import os
import numpy as np


parser = argparse.ArgumentParser()
parser.add_argument('path', metavar='vidID', type=str,
                    help='path to the superchat log file')
args = parser.parse_args()

sc_log_file = open(args.path, encoding='utf-8')

sc_log = json.load(sc_log_file)

stopwords_file = open("stopwords.txt","r")
stopwords_from_file = stopwords_file.read()
ignored_words = stopwords_from_file.split()
longstring = ""

#x, y = np.ogrid[:1000, :1000]
#mask = (x - 500) ** 2 + (y - 500) ** 2 > 400 ** 2
#mask = 255 * mask.astype(int)

for superchat in sc_log:
    if superchat["message"]:
        longstring += " "+superchat["message"]
STOPWORDS.update(ignored_words)
wordcloud = WordCloud(collocations=False, background_color="white",width=1280, height=720).generate(longstring)
print(wordcloud.words_)

plt.imshow(wordcloud, interpolation="bilinear")
plt.axis("off")
plt.show()