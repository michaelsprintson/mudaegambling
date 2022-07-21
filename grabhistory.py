
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
# Loads the .env file that resides on the same level as the script.
load_dotenv()
# Grab the API token from the .env file.
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# need to look at message 979502280300716042 and see if bolds show up and stuff
# need to get rid of bundles like 971447722815127602

from collections import defaultdict
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = discord.Client(intents=intents)

# EVENT LISTENER FOR WHEN THE BOT HAS SWITCHED FROM OFFLINE TO ONLINE.
@bot.event
async def on_ready():
	# CREATES A COUNTER TO KEEP TRACK OF HOW MANY GUILDS / SERVERS THE BOT IS CONNECTED TO.
    print("yeehaw")

    open("records.json", 'w').write("[")

    channel = bot.get_channel(967994638919163906)
    name_to_id = defaultdict(lambda: "", {m.name: m.id for m in channel.members})
    print(name_to_id)
    counter = 0
    grab_next_message = False
    past_repres = None
    async for message in channel.history(limit = None):
        if grab_next_message:
            search = re.search("(?P<term>\$[w|m|h][a|x|g])", message.content)
            if not search is None:
                past_repres[0] = message.author.id
                # print(f"{counter} - history found - {past_repres[0]} rolled {past_repres[1]} with value {past_repres[2]}")
                open("records.json", 'a').write(past_repres.__repr__()+",")

        grab_next_message = False
        past_repres = None
        counter += 1
        if (len(message.embeds) > 0) and (message.author.id == 432610292342587392): #and (message.author.name == "Mudae"): #make sure this is only from mudae
        #someone was rolled

        
            e = message.embeds[0]
            desc = message.embeds[0].description
            caller = message.interaction.user.id if not (message.interaction is None) else None

            # if not type(e.author.name) == discord.embeds._EmptyEmbed:
            try:
                if not e.author is None:
                    if not (("Like Rank" in desc or "Claim Rank" in desc) or ("Custom" in desc) or ("Harem size:" in desc) or ("Kakera" in desc) or ("TOP 1000" in e.author.name) or ("kakera" in e.author.name) or ("Kakera" in e.author.name) or ("harem" in e.author.name) or ("disablelist" in e.author.name) or ("Total value:" in desc)): #really shit way to make sure it was a roll
                        if "**" in e.description:
                            s = re.search("(?P<word>\*\*\d+\*\*)", e.description)
                            if not s is None:
                                if caller is None:
                                    grab_next_message = True
                                kval = int(s.group().strip("**"))
                                kname = e.author.name
                                current_owner = name_to_id[e.footer.text.replace("Belongs to ", "").replace("⚠️ 2 ROLLS LEFT ⚠️", "").strip().strip("·").strip()] if e.footer else ""
                                claimer = None
                                wished = None
                                if "Wished by" in message.content:
                                    print("found wish")
                                    claimer = current_owner
                                    wished = message.mentions[0].id
                                else:
                                    reactors = [u.id for r in message.reactions async for u in r.users()] if message.reactions else None
                                    if not reactors is None:
                                        if current_owner in reactors:
                                            claimer = current_owner
                                ret_dict = [caller,kname,kval,message.created_at.strftime("%m/%d/%Y, %H:%M:%S"), wished, claimer]
                                if not grab_next_message:
                                    # print(f"{counter} - historay found - {caller} rolled {kname} with value {kval}, claimer {claimer}, wished {wished}")
                                    open("records.json", 'a').write(ret_dict.__repr__()+",")
                                else:
                                    past_repres = ret_dict
            except Exception as er:
                print("error found", er)
                print("error on message", message.id)
                open("errors.txt", 'a').write(f"{message.id} \n")
    open("records.json", 'a').write("]")



bot.run(DISCORD_TOKEN)