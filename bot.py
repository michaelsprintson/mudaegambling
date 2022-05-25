
# Import the os module.
import os
import discord
import re
import json
from datetime import datetime as dt
# Import load_dotenv function from dotenv module.
from dotenv import load_dotenv
from numpy import roll
import pandas as pd
import dataframe_image as dfi
import random
import multiprocessing
import copy
# Loads the .env file that resides on the same level as the script.
load_dotenv()
# Grab the API token from the .env file.
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

prob = 0.003
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

class rollinstance():
    def __init__(self):
        print("started roll instance")
        self.start_time = dt.now()
        self.banned_ids = []
        self.rollcount = 0
    def add_roll(self, do_something):
        if (self.rollcount < 15) and (do_something):
            self.rollcount += 1
            print("rollcount updated", self.rollcount)
            if self.rollcount == 15:
                return 1
        return 0

    def is_expired(self):
        return int((dt.now() - self.start_time).seconds) > 3600

class betinstance():
    def __init__(self, id, name, channelid, outer, rollnum = 15, betval = 20, offset = 0, user_bet_on = None):
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
    def roll(self, kval, kname, bettor_id):
        
        print("betting on ", self.user_bet_on)
        print("bettor", bettor_id)
        if (self.rollcount < self.rollmax) and (True if self.user_bet_on is None else (self.user_bet_on == bettor_id)):
            print(f"bet registered - {kval}, current state - {self.rollcount, self.wincount, self.winbank}")
            self.rollcount += 1
            # print(self.offset)
            if (kval >= 100) and (self.rollcount > self.offset):
                # print('bet betted')
                # print(self.name, " won!")
                self.wincount += 1
                self.winbank.append(kname)
        if self.rollcount == self.rollmax:
            print("added to zombie at roll", self.rollcount)
            # print("betting concluded, wins = ", self.wincount, " ", self.winbank)
            self.o.bets_to_remove.append(self.uid) #0 is a code that says it might still be a zombie

class discordbot():
    def __init__(self):
        self.bet_counter = 0
        self.current_bets = {}
        self.zombie_bets = []
        self.bets_to_remove = []
        self.accouncement_queue = []
        self.current_roll_sessions = {}
        self.roll_session_zombies = {}
    def initialize_betting(self, uid, name, channel, bet_val = 20, betted_rolls = 15, offset = 0, user_bet_on = None):
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
	# CREATES A COUNTER TO KEEP TRACK OF HOW MANY GUILDS / SERVERS THE BOT IS CONNECTED TO.
	guild_count = 0

	# LOOPS THROUGH ALL THE GUILD / SERVERS THAT THE BOT IS ASSOCIATED WITH.
	for guild in bot.guilds:
		# PRINT THE SERVER'S ID AND NAME.
		print(f"- {guild.id} (name: {guild.name})")

		# INCREMENTS THE GUILD COUNTER.
		guild_count = guild_count + 1

	# PRINTS HOW MANY GUILDS / SERVERS THE BOT IS IN.
	print("SampleDiscordBot is in " + str(guild_count) + " guilds.")

# EVENT LISTENER FOR WHEN A NEW MESSAGE IS SENT TO A CHANNEL.

def process_bet(kname, kval, bet_channel_id, accepted_bet_channel = 967994638919163906, bettor_id = None):
    l.acquire()
    # print("acquiring")
    print(kname, "rolled with value", kval)
    print("current roll counts", [(n,s.rollcount) for n,s in db.current_roll_sessions.items()])


    if not bettor_id in set(db.current_roll_sessions.keys()):
        db.current_roll_sessions[bettor_id] = rollinstance()

    for currentbetname, currentbet in db.current_bets.items():
        # print(bet_channel_id, currentbet.cid, accepted_bet_channel)
        if bet_channel_id == accepted_bet_channel or currentbet.cid == bet_channel_id:
            currentbet.roll(kval, kname, bettor_id)

    for n in db.bets_to_remove:
        if n in db.current_bets:
            bet = db.current_bets[n]
            prize = (-1 - (1-(prob*bet.rnum))*(-bet.betval)) / (prob*bet.rnum)
            win = int((bet.wincount * prize) - ((bet.rnum-bet.wincount)*bet.betval))
            db.accouncement_queue.append((bet.cid, f"betting concluded, {bet.name} won = {win}! Characters qualified: {bet.winbank}"))
            print(f"added {bet.name} to announcmeents")
            db.update_balance(bet.uid, bet.name, win)
            db.current_bets.pop(n)
            if (bet.rollcount < 15):
                if (bet.user_bet_on is None):
                    db.zombie_bets.append(list([n, (15-bet.rollcount), bet]))
                else:
                    db.roll_session_zombies.append(bet)

    db.bets_to_remove = []

    db.zombie_bets = [[tup[0], tup[1]+1, tup[2]] for tup in db.zombie_bets if not tup[1] == 0]

    db.current_roll_sessions = {id:ri for id,ri in db.current_roll_sessions.items() if (ri.add_roll(id == bettor_id) == 0) and (not ri.is_expired())}
    
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
    

@bot.event
async def on_message(message):
	# CHECKS IF THE MESSAGE THAT WAS SENT IS EQUAL TO "HELLO".

    if (message.content[0:10] == "$adminecho") and (message.author.id == 138336085703917568):
        kname = message.content.split()[1]
        channel = bot.get_channel(message.channel.id)
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

    if (message.content[0:14] == "$checkbalances"):
        channel = bot.get_channel(message.channel.id)
        balances = json.load(open("balances.json", 'r'))
        ri = random.randrange(0,1000000)
        test = pd.DataFrame(balances).T.sort_values(['bal'], ascending = False).reset_index(drop=True).set_index('name')
        dfi.export(test,f"{ri}.png")
        await channel.send(file=discord.File(f"{ri}.png"))

   
    if (len(message.embeds) > 0) and (message.author.id == 432610292342587392): #and (message.author.name == "Mudae"): #make sure this is only from mudae
        #someone was rolled

        
        e = message.embeds[0]
        desc = message.embeds[0].description
        caller = message.interaction.user.id if not (message.interaction is None) else None

        # if not type(e.author.name) == discord.embeds._EmptyEmbed:
        if not (("Like Rank" in desc or "Claim Rank" in desc) or ("Custom" in desc) or ("Harem size:" in desc) or ("Kakera" in desc) or ("TOP 1000" in e.author.name) or ("kakera" in e.author.name) or ("Kakera" in e.author.name) or ("harem" in e.author.name) or ("disablelist" in e.author.name) or ("Total value:" in desc)): #really shit way to make sure it was a roll
            bet_channel_id = message.channel.id
            if "**" in e.description:
                s = re.search("(?P<word>\*\*\d+\*\*)", e.description)
                if not s is None:
                    kval = int(s.group().strip("**")) #change for wishes and owneds
                    kname = e.author.name
                    process_bet(kname, kval, bet_channel_id, bettor_id = caller)
                    await announce()

    if (message.content[0:11] == "$checkprize"):
        channel = bot.get_channel(message.channel.id)
        
        # $fakebet kval kname
        bet_channel_id = message.channel.id
        rolls = int(message.content.split()[1])
        value = int(message.content.split()[2])
        await channel.send(f"{(-1 - (1-(prob*rolls))*(-value)) / (prob*rolls)}")

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
        
        process_bet(kname, kval, bet_channel_id, bettor_id = caller)
        await announce()
    
    if (message.content[0:15] == "$adminupdatebal") and (message.author.id == 138336085703917568):
        kval = int(message.content.split()[1])
        kname = message.content.split()[2]
        db.update_balance(kname, kname, kval)

    if (message.content[0:5] == "$bet "):
        # $bet rolls val
        bet_channel_id = message.channel.id
        vflag = True
        offset = 0
        ubo = None
        try:
            mcs = message.content.split()
            rolls = int(mcs[1]) #make sure to be between 1 and 15
            value_per_roll = int(mcs[2]) #make sure to be between 1 and 20
            if len(mcs) > 3:
                if (mcs[3][0] != "<"):
                    offset = int(mcs[3])
                    print("offset is ", offset)
                else:
                    if (len(message.mentions) == 1):
                        ubo = message.mentions[0].id
                        print("ubo is", ubo)

            if (rolls + offset) > 15:
                vflag = False
                await message.add_reaction("❌")
        except Exception as e:
            print(e)
            vflag = False
            await message.add_reaction("❌")
            # channel = bot.get_channel(bet_channel_id)
            # await channel.send(f"please put in valid bet and roll numbers")

        if vflag: 
            if (rolls < 3) or (rolls > 20):
                await message.add_reaction("❌")
                # channel = bot.get_channel(bet_channel_id)
                # await channel.send(f"please put in a reasonable bet number (1-20)")
                vflag = False
            if (value_per_roll < 2) or (value_per_roll > 100):
                await message.add_reaction("❌")
                # channel = bot.get_channel(bet_channel_id)
                # await channel.send(f"please put in a reasonable bet per roll (2-100)")
                vflag = False

        if vflag:
            zflag = message.author.id in [i[0] for i in db.zombie_bets]
            general_flag = message.author.id in [bet.uid for bet in db.roll_session_zombies]
            zuflag = message.author.id in [bet.uid for bet in db.roll_session_zombies if (bet.user_bet_on == ubo)]
            if not ((message.author.id in db.current_bets) or zflag or zuflag):
                uname = message.author.name if message.author.nick is None else message.author.nick
                
                if int(db.get_current_balance(message.author.id)) > -10_000:
                    print("genflag", general_flag)
                    if not (general_flag and ubo == None):
                        db.initialize_betting(message.author.id,uname, bet_channel_id, value_per_roll, rolls, offset, user_bet_on=ubo)
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
                    remaining_rolls = 15 - db.current_roll_sessions[[bet for bet in db.roll_session_zombies if (bet.uid == message.author.id and (ubo == bet.user_bet_on))][0].user_bet_on].rollcount
                    print(remaining_rolls)
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