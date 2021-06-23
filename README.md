# YouTube Superchat analysis tools
The scripts require [this modified version of pytchat](https://github.com/KaitoCross/pytchat) that is NOT in the pip repository.

## monitoring YouTube channels to record superchats from planned livestreams
usage: `python3 monitor_livestreams.py channel_ids`  
It supports multiple channels at once by passing multiple channel IDs as parameter.  
In order to track the activity of the channel, we rely on the YouTube Data API v3. Please get yourself the appropriate API key and save it under yt_api_key.txt in the same folder as this python script.  
When it detects a planned livestream, it will start recording Superchats before the livestream starts. Once it ends, it will try to re-record superchats from the archive of the video in order to retrieve potentially previously unrecorded superchats. It automatically adds those to the statistics and logs.

## recording livestream superchats
usage: `python3 async_video_supa_analysis_v2.py video_ID`  
This can be used to record superchats from ongoing & planned livestreams & premieres as well as from broadcast/livestream recordings as long as the chat (chat replay in case of recording) is available.  
Please note that YouTube does not conserve all superchats in the chat replays. You can only get all superchats if you record during (or start recording before) the actual livestream and later record the chat replay after the stream finishes. You need to merge the two logs afterwards. `merge_sc_logs_v2.py` helps doing that.
This script also fetches some metadata of the stream, for which it needs the same API key as mentioned above in the same text file.  

## Which information regarding the superchats will be recorded
1. timestamp of message
2. user id & name of sender
3. the message text
4. the used currency
5. the amount of money donated
6. which day of the week (0-6) / hour of the day / minute of the hour it was sent on

The scripts create a folder for each YouTube Channel it comes across, using the channel ID as folder name. Within these the scripts saves the superchat logs into the sc_logs subfolder, naming the log textfile after the respective video ID + .txt  
They also save some metadata about the stream (like title, channel, start & end time, total sum of donations split by currencies) in the vid_stats subfolder of the channel folder. The filenames consist of the video ID + _stats.txt at the end.  
The stored data is JSON formatted.

## making a superchat wordcloud
usage: `python3 sc_wordcloud.py path_to_superchat_log_file path_to_mask_image`  
It generates a word cloud from a superchat log in the shape of the object in the mask image and saves a picture of the word cloud in the folder of the superchat log file. The object must be coloured. The background of the object must be pure white - all purely white areas will be detected as background.  

