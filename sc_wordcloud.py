import argparse, time, os, json, isodate
from wordcloud import WordCloud, STOPWORDS
import matplotlib.pyplot as plt
import os
import pathlib
import numpy as np


parser = argparse.ArgumentParser()
parser.add_argument('path', metavar='vidID', type=str,
                    help='The YouTube livestream/video ID')
#parser.add_argument('yt_chan_id', metavar='chanID', type=str,
                    #help='The YouTube channel ID')
args = parser.parse_args()
#videoid = args.yt_vid_id
#channel_id= args.yt_chan_id

sc_log_file = open(args.path, encoding='utf-8') #channel_id+"/sc_logs/"+videoid + ".txt.stream", encoding='utf-8')

sc_log = json.load(sc_log_file)

nichtinteressant = "_cryingmori _sleepyreap _calliye _morimurder _calliopog _glowpink _canteloupe_sandliope _canteloupe _sandliope und von Der das den wir ist die auf im _happymori _moriblush _moriguh _skull _RipHeart u _bigups aka _drunkmori"
liste_der_unerwuenschten_woerter = nichtinteressant.split()
longstring = ""

x, y = np.ogrid[:1000, :1000]

mask = (x - 500) ** 2 + (y - 500) ** 2 > 400 ** 2
mask = 255 * mask.astype(int)

for superchat in sc_log:
    if superchat["message"]:
        longstring += " "+superchat["message"]
STOPWORDS.update(liste_der_unerwuenschten_woerter)
wordcloud = WordCloud(collocations=False, background_color="white",width=1280, height=720).generate(longstring)
print(wordcloud.words_)

plt.imshow(wordcloud, interpolation="bilinear")
plt.axis("off")
plt.show()