import argparse, time, os
import json, isodate

def merge_logs(old_sc_log, new_sc_log):
	merged_sc_log = old_sc_log.copy()
	identical_msgs = 0
	new_msgs = 0
	processed = 0
	for new_entry in new_sc_log:
		processed += 1
		searchres = list(filter(lambda logentry: logentry['time'] == new_entry['time'] and logentry['userid'] == new_entry['userid'] and logentry['message'] == new_entry['message'], old_sc_log))
		if searchres:
			identical_msgs += 1
		else:
			print("New message:",new_entry)
			merged_sc_log.append(new_entry)
			new_msgs += 1
	print('messages processed:',processed)
	print('identical msgs:', identical_msgs)
	print('new msgs:', new_msgs)
	return merged_sc_log


def recount_money(sc_log):
	money_dict = {"amount_sc": 0}
	for superchat in sc_log:
		if 'currency' in superchat.keys():
			if superchat['currency'] in money_dict.keys():
				money_dict[superchat['currency']]+= superchat['value']
			else:
				money_dict[superchat['currency']] = superchat['value']
			money_dict['amount_sc'] += 1
	return money_dict


if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('old_superchat_file', metavar='oldSClog', type=str,
						help='Old superchat file')
	parser.add_argument('old_stats_file', metavar='oldStats', type=str,
						help='Old superchat stats file file')
	parser.add_argument('new_superchat_file', metavar='newSClog', type=str,
						help='new superchat file (contains the messages that need to be merged into the old file)')
	args = parser.parse_args()
	old_sc_path = args.old_superchat_file
	old_stat_path = args.old_stats_file
	new_scs_path = args.new_superchat_file
	f_old = open(old_sc_path, encoding='utf-8')
	f_old_stats = open(old_stat_path, "r")
	f_new = open(new_scs_path, "r")
	old_sc_log = json.load(f_old)
	old_vid_stats = json.load(f_old_stats)
	new_sc_log = json.load(f_new)
	merged_sc_log = merge_logs(old_sc_log,new_sc_log)
	f_merged_log = open(old_sc_path + ".merged", "w")
	f_merged_log.write(json.dumps(merged_sc_log))
	f_merged_log.close()
	merged_stats = old_vid_stats.copy()
	money_dict = recount_money(merged_sc_log)
	print(money_dict)
	merged_stats[1] = money_dict
	f_merged_stats = open(old_stat_path+".merged", "w")
	f_merged_stats.write(json.dumps(merged_stats))
	f_merged_stats.close()
	f_old.close()
	f_old_stats.close()
	f_new.close()
