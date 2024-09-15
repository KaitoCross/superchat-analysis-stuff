# YouTube Superchat analysis tools
The scripts require [this modified version of pytchat](https://github.com/KaitoCross/pytchat) that is NOT in the pip repository.

## monitoring YouTube channels to record superchats from planned livestreams
usage: `python3 monitor_livestreams.py path_to_channel_list`  
It supports multiple channels at once by passing a the path of a file that contains multiple channel IDs as parameter. The ID's in the file have to be separated by line breaks.  
In order to track the activity of the channel, we rely on either the YouTube Data API v3 or the Holodex API. If you want to use the Holodex API, you need to provide the CLI parameter `--holo_keyfile path_to_file`. To get the metadata of the YouTube videos/streams, it purely relies on the YouTube Data API. Please get yourself the appropriate API keys and save the YouTube API key under yt_api_key.txt in the same folder as this python script.  
When it detects a planned livestream, it will start recording Superchats before the livestream starts. Once it ends, it will try to re-record superchats from the archive of the video in order to retrieve potentially previously unrecorded superchats. It automatically adds those to the statistics and logs.

## recording livestream superchats
usage: `python3 async_record_running_livestream_superchats.py video_id`  
This can be used to record superchats from ongoing & planned livestreams & premieres as well as from broadcast/livestream recordings as long as the chat (chat replay in case of recording) is available.  
When it detects a planned or running livestream, it will start recording Superchats from the ongoing chat immediately. Once it ends, it will try to re-record superchats from the archive of the livestream in order to retrieve potentially previously unrecorded superchats. It automatically adds those to the statistics and logs.
This script also fetches some metadata of the stream, for which it needs the same YouTube API key as mentioned above in the same text file.  

## Which information regarding the superchats will be recorded
1. timestamp of message
2. user id & name of sender
3. the message text
4. the used currency
5. the amount of money donated
6. The superchat colour

The scripts create a folder in the `txtarchive` folder for each YouTube Channel it comes across, using the channel ID as folder name. Within these the scripts saves the superchat logs into the sc_logs subfolder, naming the log textfile after the respective video ID + .txt  
They also save some metadata about the stream (like title, channel, start & end time, total sum of donations split by currencies) in the vid_stats subfolder of the channel folder. The filenames consist of the video ID + _stats.txt at the end.  
The stored data is JSON formatted.  
All of the data is additionally stored in a postgres database which you must create by using the sql commands in `db-structure.sql`.  

## making a superchat wordcloud
You need to install mecab before using this script.
usage: `python3 sc_wordcloud.py path_to_superchat_log_file path_to_mask_image`  
It generates a word cloud from a superchat log in the shape of the object in the mask image and saves a picture of the word cloud in the folder of the superchat log file. The object must be coloured. The background of the object must be pure white - all purely white areas will be detected as background.  

## Plotting YT data
Usage: `python3 yt_meta_analysis_plot.py`
This tool uses QT and matplotlib to access the database and plot some information that was recorded through the channel monitoring and superchat recording scripts. It should be self-explanatory once you open it.

## Plotting the superchat crowd
usage: `python3 sc_crowd_intersect.py channel_ids`  
This collection includes `sc_crowd_intersect.py` which plots how the superchat donors are shared between channels as an upset-plot. Each streamer has a set of donors - this plot measures how big the intersections between those sets are. The dots indicate which intersection is being plotted above. Single dots indicate that the above plot indicates how many users have donated exclusively to the streamer marked with the single dot.