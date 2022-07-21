
# Import the os module.
import os
import discord
import re
import json
from datetime import datetime as dt
# Import load_dotenv function from dotenv module.
from dotenv import load_dotenv
import numpy as np
from math import comb
from sympy import symbols, solve
import pandas as pd
import dataframe_image as dfi
import random
import multiprocessing
import copy
from functools import reduce
from time import sleep
import ast
from collections import defaultdict
import math

from traitlets import default

BET_CHANNEL = 967994638919163906
SPAM_CHANNEL = 980201775950868532
ADMIN_ID = 138336085703917568
MUDAE_ID = 432610292342587392
DEFAULT_PROB = 0.06
DEFAULT_ROLL_NUM = 15
SELF_BOT_RUNNING = True

#todo: auto call commands with user id so they never have to again (do this on startup? do it as part of cached dict class?)


# Loads the .env file that resides on the same level as the script.
load_dotenv()
# Grab the API token from the .env file.
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")


intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)
l = multiprocessing.Lock()
annlock = multiprocessing.Lock()

num_emoji_dict = {"0":"0️⃣",
				 "1":"1️⃣",
				 "2":"2️⃣",
				 "3":"3️⃣",
				 "4":"4️⃣",
				 "5":"5️⃣",
				 "6":"6️⃣",
				 "7":"7️⃣",
				 "8":"8️⃣",
				 "9":"9️⃣"}

emojiconvert = lambda integ: [num_emoji_dict[i] for i in str(integ)]

def partial_to_full(pd):
	pd['ma'] = pd['wa'] + pd['ha']
	pd['mg'] = pd['wg'] + pd['hg']
	pd['mx'] = pd['ma'] + pd['mg']
	pd['hx'] = pd['ha'] + pd['hg']
	pd['wx'] = pd['wa'] + pd['wg']
	return pd

def partial_to_full_c(pd):
	pd.set('ma' ,pd.get('wa') + pd.get('ha'))
	pd.set('mg' ,pd.get('wg') + pd.get('hg'))
	pd.set('mx' ,pd.get('ma') + pd.get('mg'))
	pd.set('hx' ,pd.get('ha') + pd.get('hg'))
	pd.set('wx' ,pd.get('wa') + pd.get('wg'))
	return pd

class cached_dict():
	def __init__(self, storage_loc =  "storage_dicts/disable.json", intkeys = False):
		self.storage_loc = storage_loc
		self.internal_dict = {}
		if os.path.exists(storage_loc):
			stored_dict = json.load(open(storage_loc, 'r'))
			for k,d in stored_dict.items():
				if not k == "null":
					if intkeys:
						self.internal_dict[int(k)] = d
					else:
						self.internal_dict[k] = d
	
	def update_total(self, new_dict):
		self.internal_dict = new_dict
		json.dump(self.internal_dict, open(self.storage_loc, 'w'))

	def set(self, item, value):
		self.internal_dict[item] = value
		json.dump(self.internal_dict, open(self.storage_loc, 'w'))
	
	def get(self, item):
		if not item in self.internal_dict:
			self.internal_dict[item] = 0
		return self.internal_dict[item]

class rollinstance(): 
	def __init__(self, rb = 0):
		print("started roll instance")
		self.start_time = dt.now()
		self.banned_ids = []
		self.rollcount = 0
		self.rollbonus = rb
	def add_roll(self, do_something):
		if (self.rollcount < DEFAULT_ROLL_NUM + self.rollbonus) and (do_something):
			self.rollcount += 1
			# print("rollcount updated", self.rollcount)
			if self.rollcount == (DEFAULT_ROLL_NUM + self.rollbonus):
				# print("returning 1, current rollcount = ", self.rollcount)
				return 1
		return 0

	def is_expired(self):
		return int((dt.now() - self.start_time).seconds) > 3600

class betinstance():
	def __init__(self, id, name, channelid, outer, rollnum = DEFAULT_ROLL_NUM, betval = 300, offset = 0, user_bet_on = None):

		self.o = outer
		self.cid = channelid
		self.uid = id
		self.name = name
		self.rnum = rollnum
		self.rollmax = rollnum + offset
		self.betval = betval
		self.rollcount = 0
		self.wincount = 0
		self.winbank = []
		self.offset = offset
		self.user_bet_on = user_bet_on
	def roll(self, kval, kname, roll_type, roller_id):
		
		# print("betting on ", self.user_bet_on)
		# print("bettor", bettor_id)
		if (self.rollcount < self.rollmax) and (True if self.user_bet_on is None else (self.user_bet_on == roller_id)):
			print(f"bet registered - {kval}, current state - {self.rollcount, self.wincount, self.winbank}")
			self.rollcount += 1
			# print(self.offset)
			if (kval >= 100) and (self.rollcount > self.offset):
				# print('bet betted')
				# print(self.name, " won!")
				self.wincount += 1
				p = db.get_prob_for_bet(roll_type, db.disable_lists.get(roller_id)) if roller_id in db.disable_lists.internal_dict else DEFAULT_PROB
				self.winbank.append(p)
		if self.rollcount == self.rollmax:
			print("added to zombie at roll", self.rollcount)
			# print("betting concluded, wins = ", self.wincount, " ", self.winbank)
			self.o.bets_to_remove.append(self.uid) #0 is a code that says it might still be a zombie

class discordbot():
	def __init__(self, bs_loc = "../mudaescraper/big_scrape.json"):
		self.bet_counter = 0
		self.current_bets = {}
		self.zombie_bets = []
		self.bets_to_remove = []
		self.accouncement_queue = []
		self.current_roll_sessions = {}
		self.roll_session_zombies = {}

		self.roll_types = ['wa', 'ha', 'wg', 'hg', 'ma', 'mg', 'wx', 'hx', 'mx']
		self.left = cached_dict("storage_dicts/left.json")
		self.total = cached_dict("storage_dicts/total.json")
		self.total_last_scraped = (len(self.left.internal_dict) + len(self.total.internal_dict)) == 18
		self.disable_lists = cached_dict("storage_dicts/disable.json", intkeys=True)
		self.roll_nums = cached_dict("storage_dicts/roll_nums.json", intkeys=True)

		self.wish_info = cached_dict("storage_dicts/wishchances.json", intkeys=True)
		self.last_wish_caller = None

		self.calc_pool = lambda chars_left, dldsize, chars_total, p_rare: chars_left - dldsize + ((1-(chars_left/chars_total))**p_rare)*chars_total
		self.over_cien = cached_dict("storage_dicts/oc.json")
		if len(self.over_cien.internal_dict) == 0:
			self.over_cien.update_total(self.get_over_cien(bs_loc))

		self.last_db_caller = None
		self.last_wishlistt_caller = None
		self.wl_info = cached_dict("storage_dicts/wlinfo.json", intkeys=True)
		self.riddleguesses = cached_dict("storage_dicts/riddleguesses.json", intkeys=True)

		self.armandoemeraldtaxes = cached_dict("storage_dicts/armandotaxes.json", intkeys=True)
		self.totaltaxpaid = cached_dict("storage_dicts/totaltaxes.json", intkeys=True)
		self.disablebot = cached_dict("storage_dicts/ser_dl.json")
		
	def get_over_cien(self, bs_loc):
		print("calculating...")
		with open(bs_loc, "r") as f:
			data = f.readlines()[0]
		series_list = {(k:=list((d:=ast.literal_eval(i + "}}}}")).keys())[0]):d[k] for i in data.split("}}}}")[:-1]}
		char_dict = reduce(lambda a,b: {**a, **b}, [d['chars'] for k,d in series_list.items()])
		char_df = pd.DataFrame(char_dict).T
		char_df['term'] = char_df['term'].apply(lambda x: [x] if type(x) != list else x)

		search_for_char = lambda a, df: df[df['term'].apply(lambda t: sum([a in tt for tt in t]) > 0)]

		over_cien_df = char_df[char_df['val']>83]

		over_cien = {"wa":len(search_for_char('wa',over_cien_df)),
		"ha":len(search_for_char('ha',over_cien_df)),
		"ma":0,
		"wg":len(search_for_char('wg',over_cien_df)),
		"hg":len(search_for_char('hg',over_cien_df)),
		"mg":0,
		"wx":0,
		"hx":0,
		"mx":0,}
		return partial_to_full(over_cien)
	
	def get_prob_for_bet(self, bet_type, dl):

		return np.around(self.over_cien.get(bet_type)* (1-(dl[bet_type]/self.total.get(bet_type))) / self.calc_pool(self.left.get(bet_type), dl[bet_type], self.total.get(bet_type), 6), decimals = 4)
	
	def get_prob_for_wish(self, bet_type, dl, wls, wb, fwb, wp = 5000):
		# print('wp', wp)
		print('wls', wls)
		# print('wb', wb)
		# print("fwb", fwb)
		# print('left', self.left[bet_type])
		# print('total', self.total[bet_type])
		# print('disable', dl[bet_type])

		if wls == 0:
			return 0
		return np.around((1/wp) + (wls*(1 + (wb/100)) + (fwb/100)) / self.calc_pool(self.left.get(bet_type), dl[bet_type], self.total.get(bet_type), 6), decimals = 4)


	def calc_bet_multiplier(self, bet_val, prob, rolls_to_cals):
		expected_result = lambda r_n, bet_val, w_m: sum([comb(r_n,w)*((prob)**w)*((1-prob)**(r_n-w))*(-(r_b:=bet_val/r_n)*(r_n-w)+w*r_b*w_m) for w in range(0,r_n)])

		x = symbols('x')
		return solve(expected_result(rolls_to_cals, bet_val, x) + 5)[0]
		# return {i:solve(expected_result(i, bet_val,x) + 5)[0] for i in range(3,DEFAULT_ROLL_NUM+1)}

	def initialize_betting(self, uid, name, channel, bet_val = 20, betted_rolls = DEFAULT_ROLL_NUM, offset = 0, user_bet_on = None):
		# figure out how to value returns on 20 value bets across x rolls, with 15 rolls being 300 payout
		# add current bet instance with counter and list of rolls
		self.current_bets[uid] = betinstance(uid, name, channel, self, betted_rolls, bet_val, offset, user_bet_on = user_bet_on)
	
	def get_out_early(self, uid):
		if uid in self.current_bets:
			if self.current_bets[uid].rollcount == 0:
				self.current_bets.pop(uid)
			else:
				return 0
		else:
			return 0
		return 1
	
	def get_current_balance(self, uid):
		balances = json.load(open("balances.json", 'r'))
		return balances[str(uid)]['bal'] if str(uid) in balances else 0

	def update_balance(self, uid, name, change):
		balances = json.load(open("balances.json", 'r'))
		if str(uid) in list(balances.keys()):
			balances[str(uid)]['bal'] += change
		else:
			balances[str(uid)] = {'bal':change, 'name':name}
		json.dump(balances, open("balances.json", 'w'))

	def all_balances(self):
		return json.load(open("balances.json", 'r'))

db = discordbot()

# EVENT LISTENER FOR WHEN THE BOT HAS SWITCHED FROM OFFLINE TO ONLINE.
@bot.event
async def on_ready():
	print("bot ready")
	# ch = bot.get_channel(980201775950868532)
	# await ch.send("$dl")
	# sleep(1)
	# await ch.send("$left")


# EVENT LISTENER FOR WHEN A NEW MESSAGE IS SENT TO A CHANNEL.

def process_bet(kname, kval, roll_type, bet_channel_id, accepted_bet_channel = BET_CHANNEL, roller_id = None):
	l.acquire()
	# print("acquiring")
	print(kname, "rolled with value", kval)
	print("current roll counts", [(n,s.rollcount) for n,s in db.current_roll_sessions.items()])


	if not roller_id in set(db.current_roll_sessions.keys()):
		db.current_roll_sessions[roller_id] = rollinstance((int(db.roll_nums.get(roller_id)) if roller_id in db.roll_nums.internal_dict else 0))

	for currentbetname, currentbet in db.current_bets.items():
		# print(bet_channel_id, currentbet.cid, accepted_bet_channel)
		if bet_channel_id == accepted_bet_channel or currentbet.cid == bet_channel_id:
			currentbet.roll(kval, kname, roll_type, roller_id)

	for n in db.bets_to_remove:
		if n in db.current_bets:
			bet = db.current_bets[n]
			p = DEFAULT_PROB
			rolling_win_count = 0			
			if db.total_last_scraped:
				# if roll_type in db.roll_types:
				for p in bet.winbank:
					print(bet.betval, p, bet.rnum)
					print("won an additional", db.calc_bet_multiplier(bet.betval, p, bet.rnum) * (bet.betval / bet.rnum), "from", p)
					rolling_win_count += db.calc_bet_multiplier(bet.betval, p, bet.rnum) * (bet.betval / bet.rnum)
					
			
			# print(f"probability for {roll_type} is {p}, prize is {prize}")
			win = int(rolling_win_count - ((bet.rnum-bet.wincount)*(bet.betval/bet.rnum)))
			db.accouncement_queue.append((bet.cid, f"betting concluded, {bet.name} won = {win}! Characters qualified: {bet.winbank}"))
			print(f"added {bet.name} to announcmeents")
			db.update_balance(bet.uid, bet.name, win)
			db.current_bets.pop(n)
			if (bet.rollcount < DEFAULT_ROLL_NUM): 
				if (bet.user_bet_on is None):
					db.zombie_bets.append(list([n, (DEFAULT_ROLL_NUM-bet.rollcount), bet]))
				else:
					db.roll_session_zombies.append(bet)

	db.bets_to_remove = []

	db.zombie_bets = [[tup[0], tup[1]-1, tup[2]] for tup in db.zombie_bets if not tup[1] == 0]

	db.current_roll_sessions = {id:ri for id,ri in db.current_roll_sessions.items() if (ri.add_roll(id == roller_id) == 0) and (not ri.is_expired())}
	
	db.roll_session_zombies = [i for i in db.roll_session_zombies if (i.user_bet_on in db.current_roll_sessions)]
	
	# print("releasing")
	l.release()

async def announce():
	annlock.acquire()
	localann = copy.copy(db.accouncement_queue)
	db.accouncement_queue = []
	annlock.release()
	for ann in localann:
		channel = bot.get_channel(ann[0])
		await channel.send(ann[1])
	
async def get_command(chid, cmd, id):
	channel = bot.get_channel(chid)
	if SELF_BOT_RUNNING:
		await channel.send(f"getting {cmd} information ...")
		channel = bot.get_channel(SPAM_CHANNEL)
		await channel.send(f"$botecho ${cmd} {id}")
		if (cmd == "dl"):
			db.last_db_caller = id
		
		if (cmd == "bonus"):
			db.last_wish_caller = id
		
		if (cmd == "wlt"):
			db.last_wishlistt_caller = id
	else:
		await channel.send(f"please run ${cmd} to view this information")


@bot.event
async def on_message(message):
	# CHECKS IF THE MESSAGE THAT WAS SENT IS EQUAL TO "HELLO".

	if (message.content[0:10] == "$adminecho") and (message.author.id == ADMIN_ID):
		kname = reduce(lambda a,b:a+" "+b, message.content.split()[1:])
		channel = bot.get_channel(967994638919163906)
		await channel.send(f"{kname}")

	if (message.content[0:9] == "$buyclaim"):
		channel = bot.get_channel(message.channel.id)
		try:
			id_to_claim = message.reference.message_id
		except Exception as e:
			await channel.send(f"needs to be a reply to a message")
		msg = channel.get_partial_message(id_to_claim)
		await msg.add_reaction("🔥")

	if (message.content[0:13] == "$checkbalance"):
		bal = db.get_current_balance(message.author.id)
		channel = bot.get_channel(message.channel.id)
		await channel.send(f"{message.author.name}'s balance is {bal}")

	if (message.content[0:14] == "$leaderboard"):
		channel = bot.get_channel(message.channel.id)
		balances = json.load(open("balances.json", 'r'))
		ri = random.randrange(0,1000000)
		test = pd.DataFrame(balances).T.sort_values(['bal'], ascending = False).reset_index(drop=True).set_index('name')
		dfi.export(test,f"{ri}.png")
		await channel.send(file=discord.File(f"{ri}.png"))
		
	if (message.content[0:10] == "$betcancel"):
		response = db.get_out_early(message.author.id)
		if response == 1:
			await message.add_reaction("✅")
		else:
			await message.add_reaction("❌")
	
	if (message.content[0:8] == "$fakebet"):
		caller = message.author.id
		# $fakebet kval kname
		bet_channel_id = message.channel.id
		kval = int(message.content.split()[1])
		kname = message.content.split()[2]
		rolltype = message.content.split()[3]
		
		process_bet(kname, kval, rolltype, bet_channel_id, roller_id = 44444)
		await announce()
	
	if (message.content[0:15] == "$adminupdatebal") and (message.author.id == ADMIN_ID):
		kval = int(message.content.split()[1])
		kname = message.content.split()[2]
		db.update_balance(kname, kname, kval)

	if (message.content[0:6] == "$guess"):
		if message.author.id in set(db.riddleguesses.internal_dict.keys()):
			db.riddleguesses.set(message.author.id, {'name':message.author.display_name, 'guess_count': 1 + int(db.riddleguesses.get(message.author.id)['guess_count'])})
		else:
			db.riddleguesses.set(message.author.id, {'name':message.author.display_name, 'guess_count':1})
		kname = message.content[6:]
		if len(kname) < 20:
			if ('rick' in kname) and ("roll" in kname):
				await message.add_reaction("✅")
			else:
				await message.add_reaction("❌")
		else:
			await message.add_reaction("❌")


	if (message.content[0:14] == "$riddlecounts"):
		channel = bot.get_channel(message.channel.id)
		balances = json.load(open("storage_dicts/riddleguesses.json", 'r'))
		ri = random.randrange(0,1000000)
		test = pd.DataFrame(balances).T.sort_values(['guess_count'], ascending = False).reset_index(drop=True).set_index('name')#.reset_index(drop=True).set_index('index')
		dfi.export(test,f"pic/{ri}.png")
		await channel.send(file=discord.File(f"pic/{ri}.png"))


	if (message.author.id == MUDAE_ID):
		if ("<:addroll:633217436044492801>" in message.content):
			add_roll_line = [i for i in message.content.split("\n") if "<:addroll:633217436044492801>" in i][0]
			s = re.search("\*\*\+(?P<adrolls>\d+)\*\*", add_roll_line).group("adrolls")
			db.roll_nums.set(db.last_wish_caller, s)
		if ("<:wlslot:633217442151137280>" in message.content):
			all_lines = [i for i in message.content.split("\n") if "<:wlslot:633217442151137280>" in i]
			wl_slots = 7
			extra_p = 0
			extra_fw_p = 0
			for l in all_lines:
				if "Wishlist slots:" in l:
					s = re.search("\*\*\+(?P<wlslots>\d+)\*\*", l)
					if not s is None:
						wl_slots += int(s.group('wlslots'))
				if "Spawn bonus for wishes:" in l:
					s = re.search("\*\*\+(?P<wlslots>\d+)\%\*\*", l)
					if not s is None:
						extra_p = int(s.group('wlslots'))
				if "$firstwish" in l:
					s = re.search("\*\*\+(?P<wlslots>\d+)\%\*\*", l)
					if not s is None:
						extra_fw_p = int(s.group('wlslots'))
			db.wish_info.set(db.last_wish_caller, [wl_slots, extra_p, extra_fw_p])
			await message.add_reaction("✅")

		if ("<:Phosph:498523296799653889> **Including:**" in message.content):
			ls = [i.split(">")[1] for i in message.content.split("\n\n")[0].split("\n")]
			found_num = [int(i) for i in re.findall("\d+",ls[0])]
			db.left.set('wa', found_num[0])
			db.total.set('wa', found_num[1])
			db.left.set('wg', found_num[2])
			db.total.set('wg', found_num[3])
			found_num = [int(i) for i in re.findall("\d+",ls[1])]
			db.left.set('ha', found_num[0])
			db.total.set('ha', found_num[1])
			db.left.set('hg', found_num[2])
			db.total.set('hg', found_num[3])

			partial_to_full_c(db.left)
			partial_to_full_c(db.total)

			print("left and total dictionaries acquired")
			await message.add_reaction("✅")
			db.total_last_scraped = True

	if (message.content == "$dl") or (message.content == "$disablelist"):
		db.last_db_caller = message.author.id
	
	if (message.content == "$bonus"):
		db.last_wish_caller = message.author.id
	
	if (message.content == "$wlt"):
		db.last_wishlistt_caller = message.author.id
	elif (message.content[0:4] == "$wlt") and (len(message.mentions) == 0):
		db.last_wishlistt_caller = int(message.content.split(" ")[1])

	if (len(message.embeds) > 0) and (message.author.id == MUDAE_ID):
		e = message.embeds[0]
		if (not e.author.name is None) and (not e.author is None):
			if ('wishlist' in e.author.name) and (not db.last_wishlistt_caller is None):
				fs = message.embeds[0].description.split("\n\n")[0]
				ser_dict = defaultdict(int)
				charstrings = message.embeds[0].description.split("\n\n")[1].split("\n")
				for charstring in charstrings:
					find_ser = re.search("\*\* - (?P<sername>[^;]*) \*\(", charstring)
					if not find_ser is None:
						sername = find_ser.group("sername")
						ser_dict[sername] += 1
				db.disablebot.set(db.last_wishlistt_caller, ser_dict)
				found_num = [int(i) for i in re.findall("\d+",fs)]
				db.wl_info.set(db.last_wishlistt_caller, {})
				db.wl_info.get(db.last_wishlistt_caller)['wa'] = found_num[0]
				db.wl_info.get(db.last_wishlistt_caller)['ha'] = found_num[1]
				db.wl_info.get(db.last_wishlistt_caller)['wg'] = found_num[2]
				db.wl_info.get(db.last_wishlistt_caller)['hg'] = found_num[3]
				db.wl_info.set(db.last_wishlistt_caller, partial_to_full(db.wl_info.get(db.last_wishlistt_caller)))
				print("wish list info acquired for user", db.last_wishlistt_caller)
				await message.add_reaction("✅")
				db.last_wishlistt_caller = None
			if 'disablelist' in e.author.name:
				fs = message.embeds[0].description.split("\n\n")[0].split("\n")[0]
				found_num = [int(i) for i in re.findall("\d+",fs)][1:]
				db.disable_lists.set(db.last_db_caller, {})
				db.disable_lists.get(db.last_db_caller)['wa'] = found_num[0]
				db.disable_lists.get(db.last_db_caller)['ha'] = found_num[1]
				db.disable_lists.get(db.last_db_caller)['wg'] = found_num[2]
				db.disable_lists.get(db.last_db_caller)['hg'] = found_num[3]
				db.disable_lists.set(db.last_db_caller, partial_to_full(db.disable_lists.get(db.last_db_caller)))
				ch = bot.get_channel(message.channel.id)
				print("disable dictionaries acquired for user", db.last_db_caller)
				await message.add_reaction("✅")
				db.last_db_caller = None








	if (message.content[0:10] == "$checkprob"):
		channel = bot.get_channel(message.channel.id)
		
		# $fakebet kval kname
		bet_channel_id = message.channel.id
		mcs = message.content.split()
		roll_type = mcs[1]

		if len(mcs) > 2:
			rolls = int(mcs[2])
			value = int(mcs[3])

		infoaqbool = False
		if not db.total_last_scraped:
			await get_command(bet_channel_id, "left", None)
			sleep(2)
			infoaqbool = True
		if not message.author.id in set(db.disable_lists.internal_dict.keys()):
			await get_command(bet_channel_id, "dl", message.author.id)
			sleep(2)
			infoaqbool = True


		if infoaqbool:
			await channel.send(f"please repeat the command now that all information is accessible to the bot")
		else:
			if roll_type in db.roll_types:
				
				p = db.get_prob_for_bet(roll_type, db.disable_lists.get(message.author.id))
				if len(mcs) > 2:
					b = db.calc_bet_multiplier(value, p, rolls) * (value / rolls)
						
					await channel.send(f"{np.around(p*100, decimals=4)}, bet prize: {int(b)}")
				else:
					await channel.send(f"{np.around(p*100, decimals=4)}")

			else:
				await channel.send(f"please input a valid roll type (dont use $)")
	
	if (message.content[0:14] == "$checkwishprob"):
		channel = bot.get_channel(message.channel.id)
		
		# $fakebet kval kname
		bet_channel_id = message.channel.id
		mcs = message.content.split()
		roll_type = mcs[1]
		wish_list_num = int(mcs[2]) if len(mcs) == 3 else None

		infoaqbool = False
		if not db.total_last_scraped:
			await get_command(bet_channel_id, "left", None)
			sleep(2)
			infoaqbool = True
		if not message.author.id in set(db.disable_lists.internal_dict.keys()):
			await get_command(bet_channel_id, "dl", message.author.id)
			sleep(2)
			infoaqbool = True
		if not message.author.id in set(db.wish_info.internal_dict.keys()):
			await get_command(bet_channel_id, "bonus", message.author.id)
			sleep(2)
			infoaqbool = True
		if not message.author.id in set(db.wl_info.internal_dict.keys()):
			await get_command(bet_channel_id, "wlt", message.author.id)
			sleep(2)
			infoaqbool = True

		if infoaqbool:
			await channel.send(f"please repeat the command now that all information is accessible to the bot")
		else:
			if roll_type in db.roll_types:
				wish_info_list = db.wish_info.get(message.author.id)
				wls = int(db.wl_info.get(message.author.id)[roll_type]) if wish_list_num is None else wish_list_num
				p = db.get_prob_for_wish(roll_type, db.disable_lists.get(message.author.id), wls, wish_info_list[1], wish_info_list[2])
				num_rolls = (int(db.roll_nums.get(message.author.id)) if message.author.id in db.roll_nums.internal_dict else 0) + DEFAULT_ROLL_NUM
				prob_fifteen = sum([(math.factorial(num_rolls) / (math.factorial(num_rolls-z) * math.factorial(z))) * ((p)**z) * ((1-p)**(num_rolls-z)) for z in range(1,num_rolls)])
				await channel.send(f"for {wls} wished items of type {roll_type}: {np.around(p*100, decimals=4)} percent, across {num_rolls} rolls: {np.around(prob_fifteen*100, decimals=4)} percent")
			else:
				await channel.send(f"please input a valid roll type (dont use $)")





	## change these two to support multiple taxees
	## add the ability to grab all users in a channel and generate id to username mapping
	if (message.content[:16] == "$adminresettaxes") and (message.author.id == ADMIN_ID):
		id_to_reset = int(message.content[17:])
		db.armandoemeraldtaxes.set(id_to_reset, 0)


	if (message.content == "$checktaxes"):
		if (message.author.id == ADMIN_ID):
			await message.reply(content = db.armandoemeraldtaxes.internal_dict.__repr__())
		else:
			await message.reply(content = db.armandoemeraldtaxes.get(message.author.id))

	if (message.content == "$totaltaxpaid"):
		if (message.author.id == ADMIN_ID):
			await message.reply(content = db.totaltaxpaid.internal_dict.__repr__())
		else:
			await message.reply(content = db.totaltaxpaid.get(message.author.id))

	if (message.author.id == MUDAE_ID) and ("(Emerald IV bonus)" in message.content):
		s = re.search("\*\*\+(?P<wlslots>\d+)\*\*", message.content)
		if not s is None:
			val = int(s.group("wlslots"))
			if ("armadillo" in message.content):
				taxes = np.around(val * 0.20)
				db.totaltaxpaid.set(279870739451084800, db.totaltaxpaid.get(279870739451084800) + taxes)
				db.armandoemeraldtaxes.set(279870739451084800, db.armandoemeraldtaxes.get(279870739451084800) + taxes)
			if ("lilabeth" in message.content):
				taxes = np.around(val * 0.50)
				db.totaltaxpaid.set(469706380220170240, db.totaltaxpaid.get(469706380220170240) + taxes)
				db.armandoemeraldtaxes.set(469706380220170240, db.armandoemeraldtaxes.get(469706380220170240) + taxes)
			if ("Chaosfnog" in message.content):
				taxes = np.around(val * 0.50)
				db.totaltaxpaid.set(88020501930209280, db.totaltaxpaid.get(88020501930209280) + taxes)
				db.armandoemeraldtaxes.set(88020501930209280, db.armandoemeraldtaxes.get(88020501930209280) + taxes)
			

   
	if (len(message.embeds) > 0) and (message.author.id == MUDAE_ID): #and (message.author.name == "Mudae"): #make sure this is only from mudae
		#someone was rolled

		
		e = message.embeds[0]
		desc = message.embeds[0].description
		caller = message.interaction.user.id if not (message.interaction is None) else None

		# if not type(e.author.name) == discord.embeds._EmptyEmbed:
		if not ((e.author is None) or (e.author.name is None) or (message.interaction) is None):
			if not (("Like Rank" in desc or "Claim Rank" in desc) or ("Custom" in desc) or ("Harem size:" in desc) or ("Kakera" in desc) or ("TOP 1000" in e.author.name) or ("kakera" in e.author.name) or ("Kakera" in e.author.name) or ("harem" in e.author.name) or ("disablelist" in e.author.name) or ("Total value:" in desc)): #really shit way to make sure it was a roll
				bet_channel_id = message.channel.id
				if "**" in e.description:
					s = re.search("(?P<word>\*\*\d+\*\*)", e.description)
					if not s is None:
						kval = int(s.group().strip("**")) #change for wishes and owneds
						kname = e.author.name
						process_bet(kname, kval, message.interaction.name.strip(), bet_channel_id, roller_id = caller)
						await announce()

	

	if (message.content[0:5] == "$bet "):
		# $bet rolls val
		bet_channel_id = message.channel.id
		channel = bot.get_channel(message.channel.id)
		vflag = True
		offset = 0
		ubo = message.mentions[0].id if (len(message.mentions) == 1) else None
		try:
			mcs = message.content.split()
			rolls = int(mcs[1]) #make sure to be between 1 and default roll num (can grow to num of rolls a player has)
			total_bet = int(mcs[2]) #make sure to be between 1 and 20
			if len(mcs) > 3:
				if (mcs[3][0] != "<"):
					offset = int(mcs[3])
					# print("offset is ", offset)
				else:
					print("grabbing ubo")
					
						# print("ubo is", ubo)
			max_roll = DEFAULT_ROLL_NUM if ubo is None else DEFAULT_ROLL_NUM + (int(db.roll_nums.get(ubo)) if ubo in db.roll_nums.internal_dict else 0)
			if (rolls + offset) > max_roll:
				vflag = False
				await message.add_reaction("❌")
		except Exception as e:
			print(e)
			vflag = False
			await message.add_reaction("❌")
			# channel = bot.get_channel(bet_channel_id)
			# await channel.send(f"please put in valid bet and roll numbers")
		print(f"offset - {offset}, ubo - {ubo}")
		if vflag: 
			
			if (rolls < 3) or (rolls > max_roll): 
				await message.add_reaction("❌")
				# channel = bot.get_channel(bet_channel_id)
				# await channel.send(f"please put in a reasonable bet number (1-20)")
				vflag = False
			if (total_bet < 100) or (total_bet > 1500):
				await message.add_reaction("❌")
				# channel = bot.get_channel(bet_channel_id)
				# await channel.send(f"please put in a reasonable bet per roll (2-100)")
				vflag = False

		
		t = [(DEFAULT_ROLL_NUM + rs.rollbonus) - rs.rollcount for n, rs in db.current_roll_sessions.items() if (n == ubo)]
		# print(t)
		if len(t) > 0:
			# print(t[0])
			if rolls > t[0]:
				vflag = False

		if vflag:
			zflag = message.author.id in [i[0] for i in db.zombie_bets if i[1] != 0]
			general_flag = message.author.id in [bet.uid for bet in db.roll_session_zombies]
			zuflag = message.author.id in [bet.uid for bet in db.roll_session_zombies if (bet.user_bet_on == ubo)]
			if not ((message.author.id in db.current_bets) or zflag or zuflag):
				uname = message.author.name if message.author.nick is None else message.author.nick
				
				if int(db.get_current_balance(message.author.id)) > -10_000:
					# print("genflag", general_flag)
					if not (general_flag and ubo == None):
						db.initialize_betting(message.author.id,uname, bet_channel_id, total_bet, rolls, offset, user_bet_on=ubo)
							# if roll_type in db.roll_types:
						if not ubo is None:
							dl = int(ubo) in [int(i) for i in list(db.disable_lists.internal_dict.keys())]
							if not dl:
								await channel.send(f"Note: until the person bet on calls $dl, all rolls for this bet will be handled with default probability")
						if not db.total_last_scraped:
							await channel.send(f"Note: until $left is called, all rolls for this bet will be handled with default probability")
						print(f"betting started for user {message.author.id}" + ("" if ubo is None else f" on {ubo}"))
							
						# channel = bot.get_channel(bet_channel_id)
						await message.add_reaction("✅")
					else:
						await message.add_reaction("⏸️")
				else:
					await message.add_reaction("❌")
				# await channel.send(f"betting started for user {uname}")
			else:
				if zflag:
					print("zflag tripped")
					await message.add_reaction("⏸️")
					remaining_rolls = int([b[1] for b in db.zombie_bets if b[0] == message.author.id][0]) + 1
					if remaining_rolls == 11:
						await message.add_reaction("🕚")
					else:
						for e in emojiconvert(remaining_rolls):
							await message.add_reaction(e)
				elif zuflag: 
					print("zuflag tripped")
					await message.add_reaction("⏸️")
					remaining_rolls = DEFAULT_ROLL_NUM + (int(db.roll_nums.get(ubo)) if ubo in db.roll_nums.internal_dict else 0) - db.current_roll_sessions[[bet for bet in db.roll_session_zombies if (bet.uid == message.author.id and (ubo == bet.user_bet_on))][0].user_bet_on].rollcount
					if remaining_rolls == 11:
						await message.add_reaction("🕚")
					else:
						for e in emojiconvert(remaining_rolls):
							await message.add_reaction(e)
				else:
					await message.add_reaction("♻️")
				# channel = bot.get_channel(bet_channel_id)
				# await channel.send(f"betting already exists for user {uname}")


bot.run(DISCORD_TOKEN)