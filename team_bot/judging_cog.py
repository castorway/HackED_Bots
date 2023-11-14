import discord
from discord.ext import commands
from typing import Optional
from discord.utils import get as dget
import logging
from datetime import datetime
import utils
import random
import os
import json
from pathlib import Path
import asyncio
from pprint import pformat
import itertools
import numpy as np
from queuing import queue_algorithm

config = utils.general_setup()

# set up dirs for json files
file_path = Path(os.path.realpath(__file__)).parents[0] # path to this directory
data_dir = file_path / "judging"
os.makedirs(data_dir, exist_ok=True)


# global storing current judging dict; room ids mapped to position and list of team names
current_judging = {}


def gen_filename(tag, ext):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return data_dir / f"{tag}_{timestamp}.{ext}"


def check_author_perms(ctx):
    """ All the commands in this cog should only be usable by users with the organizer role. """
    for role in ctx.author.roles:
        if role.id == config['roles']['organizer']:
            return True
    else:
        return False


async def send_as_json(ctx, dictionary, filename):
    temp_name = Path("./_temp.json")

    # make file
    save_filename = gen_filename("generated", "json")
    with open(save_filename, "w") as f:
        f.write(json.dumps(dictionary, indent=4))

    # send file
    await ctx.send(file=discord.File(save_filename, filename=filename))


class Judging(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.judging = {}

        self.judging_medium_msg = None
        self.judging_category_msg = None


    def pprint_judging(self, judging=None):
        msg = "```asciidoc\n"
        msg += f"JUDGING\n"
        msg += f"==========================\n"
        msg += f"Note that the team highlighted in blue is the *current team* that is being judged (if any). The team after it is the team that will be pinged when `next <room_id>` is run.\n"

        if judging == None:
            judging = self.judging

        for room_id, info in judging.items():
            # room status
            if info['next_team'] == 0:
                status = "Not Started"
            elif info["next_team"] < len(info["teams"]):
                status = "In Progress"
            else:
                status = "Done"
            
            msg += f"\n{'[' + room_id + ']' :16} | next={info['next_team']} ({status})\n"

            # print each team
            for i, team_name in enumerate(judging[room_id]["teams"]):
                if i == info["next_team"] - 1:
                    msg += f"= {team_name} =\n"
                else:
                    msg += f"* {team_name}\n"
        
        msg += "```"
        
        return msg


    def my_log(self, log_file, txt):
        with open(log_file, "a") as f:
            f.write(txt + "\n")

    
    async def send_in_judging_log(self, ctx, txt):
        channel = dget(ctx.message.guild.channels, id=config['judging_log_channel_id']) # get log channel
        await channel.send(txt)


    async def get_confirmation(self, confirm_user, confirm_msg):
        await confirm_msg.add_reaction("✅")
        await confirm_msg.add_reaction("❌")
        # TODO: consider char limit

        def check(reaction, user):
            return user == confirm_user and reaction.emoji in ["✅", "❌"]

        # waiting for reaction confirmation
        try:
            reaction, user = await self.bot.wait_for('reaction_add', check=check, timeout=20.0) # 20 second timeout
        except asyncio.TimeoutError:
            await confirm_msg.reply("Timed out waiting for confirmation; rerun the command if you want to try again.")
            return None

        if reaction.emoji == "✅":
            return True
        else:
            return False
    

    @commands.command(help=f'''Usage: ~set_judging_react_messages <#channel> <medium_message_id> <category_message_id>''')
    async def set_judging_react_messages(self, ctx, channel: discord.TextChannel, medium_msg_id: str, category_msg_id: str):
        ''' Adds reactions to two messages to act as judging medium (online/inperson) and special categories reaction choice menus. '''

        if not check_author_perms(ctx): return
        logging.info(f"set_judging_react_messages called with channel={channel}, medium_msg_id={medium_msg_id}, category_msg_id={category_msg_id}.")
        
        # verify both messages exist
        try:
            medium_msg = await channel.fetch_message(medium_msg_id)
            category_msg = await channel.fetch_message(category_msg_id)
        except discord.error.NotFound as e:
            await ctx.message.add_reaction("❌")
            await ctx.reply("Messages were not set; one or both messages could not be found. Check the channel and IDs again.")

        # medium (online or inperson)
        await medium_msg.add_reaction(config["inperson_react"])
        await medium_msg.add_reaction(config["online_react"])
        
        # special categories
        for cat, info in config["judging_categories"].items():
            # no reaction for default category
            if cat != "default":
                await category_msg.add_reaction(info["react"])

        self.judging_medium_msg = medium_msg
        self.judging_category_msg = category_msg

        logging.info(f"Set judging_medium_msg={self.judging_medium_msg}")
        logging.info(f"Set judging_category_msg={self.judging_category_msg}")
        await ctx.message.add_reaction("✅")


    async def get_team_reacts(self, message, accepted_icons):
        ''' Given a message, get the reactions to it in a dictionary separated by team. '''
        team_choices = {} # map team_name : [emojis reacted by team members]

        for reaction in message.reactions:

            # ignore invalid reacts
            if reaction.emoji not in accepted_icons:
                logging.info(f"get_team_reacts: ignored reactions with emoji {reaction.emoji}")
                continue

            # get all the users that added this reaction
            user_list = []
            async for user in reaction.users():
                if user != self.bot.user and not user.bot:
                    user_list.append(user)

            logging.info(f"get_team_reacts: looking at reaction={reaction}, user_list={[u.name for u in user_list]}")

            # add info to team choice dict
            for user in user_list:
                # find user's team
                for role in user.roles:
                    if role.colour == config['team_role_colour_obj']:
                        # role.name is the team name
                        if role.name not in team_choices.keys():
                            team_choices[role.name] = [reaction.emoji]
                        else:
                            team_choices[role.name].append(reaction.emoji)
                        break
                else:
                    # member not in team
                    logging.info(f"get_team_reacts: ignored user {user} reacted with {reaction.emoji}, but has no team")

        logging.info(team_choices)
        return team_choices


    @commands.command(help=f'''Usage: `{config['prefix']}auto_make_queues`.''')
    async def auto_make_queues(self, ctx):
        '''
        Automatically generate judging queues for judging rooms defined in config.json, based on the 
        reactions to self.judging_medium_msg and self.judging_category_msg.
        
        Requires `set_judging_react_messages` to have been run first.
        '''

        if not check_author_perms(ctx): return
        logging.info(f"auto_make_queues called.")

        # check we have the messages necessary to make queues
        if self.judging_medium_msg == None or self.judging_category_msg == None:
            await ctx.message.add_reaction("❌")
            await ctx.reply("Judging medium and category messages haven't been set yet. Ensure you run `set_judging_react_messages` before this command.")

        # add special queue logger just for this <3
        root_logger = logging.getLogger()
        main_log_handler = root_logger.handlers[0]
        root_logger.removeHandler(main_log_handler) # remove the main log handler temporarily

        queue_log_name = gen_filename("autoqueue", ".txt")
        queue_log_handler = logging.FileHandler(queue_log_name)
        formatter = logging.Formatter('%(message)s')
        queue_log_handler.setFormatter(formatter)
        root_logger.addHandler(queue_log_handler)

        # get information from messages

        medium_icons = [config["inperson_react"], config["online_react"]]
        category_icons = [info["react"] for cat, info in config["judging_categories"].items() if cat != "default"]

        logging.info("===== get_team_reacts =====")
        team_medium_reacts = await self.get_team_reacts(self.judging_medium_msg, accepted_icons=medium_icons)
        team_category_reacts = await self.get_team_reacts(self.judging_category_msg, accepted_icons=category_icons)
        logging.info("===========================")

        logging.info("Reactions pulled from the judging messages, by-team:")
        logging.info(pformat(team_medium_reacts, indent=4))
        logging.info(pformat(team_category_reacts, indent=4))

        # get all teams that reacted to either message
        all_judgable_teams = list(set(list(team_medium_reacts.keys()) + list(team_category_reacts.keys())))

        # === make some handy dicts

        icon_to_category = {info["react"]: cat for cat, info in config["judging_categories"].items() if cat != "default"}

        team_medium_pref = {} # map team to their preferred judging medium (online/inperson)
        team_category_choice = {} # map team to all categories they reacted to (as icons)
        
        for team_name in all_judgable_teams:
            # if someone reacted to category but not medium, give them default medium
            if team_name not in team_medium_reacts.keys():
                team_medium_pref[team_name] = config["default_judging_medium_pref"]
            elif config["online_react"] in team_medium_reacts[team_name]:
                team_medium_pref[team_name] = "online"
            else:
                team_medium_pref[team_name] = "inperson"
            
            # get unique categories chosen
            team_category_choice[team_name] = [icon_to_category[e] for e in list(set(team_category_reacts[team_name]))]

        # icon_to_category = {info["react"]: cat for cat, info in config["judging_categories"].items() if cat != "default"}

        # map choice of (category, medium) to teams
        judging = queue_algorithm(team_category_choice, team_medium_pref)
        
        # remove special queue logger
        logging.info("Finished auto-generating queue.")
        queue_log_handler.close()
        root_logger.removeHandler(queue_log_handler)
        root_logger.addHandler(main_log_handler)

        # send info message
        await ctx.reply("This is a json file mapping the *room ID* (as specified in the config.json for this bot) to a list of *team names* (as in the Discord roles), as well as a txt log file for the algorithm. Check the txt log file to make sure everything looks right, modify the json as desired, and then use the json to start judging with the `start_judging` command (be careful with that though).")

        # send generated queue
        await send_as_json(ctx, judging, filename="judging_breakdown.json")

        await ctx.send(file=discord.File(queue_log_name, filename="queue_log.txt"))


    @commands.command(help=f'''Usage: `{config['prefix']}start_judging`.''')
    async def start_judging(self, ctx):

        if not check_author_perms(ctx):
            return

        logging.info(f"start_judging called.")

        # normally checking for extraneous arguments wouldn't be important; i check them here because
        # this is a sensitive command and incorrect usage might mean someone's messed something up in
        # such a way that would cause judging to not go how they want
        if ctx.message.content.strip() != "~start_judging" \
            or len(ctx.message.attachments) != 1 \
            or not ctx.message.attachments[0].filename.endswith(".json"):

            await ctx.message.add_reaction("❌")
            await ctx.reply("Judging was not started; this command must be called with no arguments and exactly one attachment (a json in the same format output by `auto_make_queues`).")

        # download the attachment
        # im not a security expert but i can see this being a bit of a hazard. please do not hack my bot
        filename = gen_filename("received", "json")
        
        with open(filename, "wb") as f:
            await ctx.message.attachments[0].save(fp=f)

        # validate file
        try:
            with open(filename, "r") as f:
                judging = json.loads(f.read())

            # get all teams for validation purposes
            all_teams = await utils.get_all_team_roles(ctx)
            team_names = [role.name for role in all_teams]

            # some lazy validation. can't really check every possible issue here.
            for room_id in judging.keys():
                assert room_id in list(config["judging_rooms"].keys()), f"room id {room_id} not in config"
                assert 0 <= judging[room_id]["next_team"], f"for room id {room_id}, next_team {judging[room_id]['next_team']} is invalid"

                if len(judging[room_id]["teams"]) > 0:
                    assert judging[room_id]["next_team"] < len(judging[room_id]["teams"]), f"for room id {room_id}, next_team {judging[room_id]['next_team']} is invalid"
                
                for name in judging[room_id]["teams"]:
                    assert name in team_names, f"team name {name} in room id {room_id} does not exist"

        except (ValueError, AssertionError, KeyError) as e:
            # catch any issues, log them, and send to user
            logging.error(e)
            logging.info("Unable to read json.")

            await ctx.message.add_reaction("❌")
            await ctx.reply(f"Judging was not started; there's likely something wrong with your json. Make sure it matches the format of the output of `setup_queues`.\nError message: `{e}`")

        # get confirmation
        msg = "This is the judging scheme that you are about to switch to. Verify it is correct, and then react to this message with ✅ to confirm, or ❌ to cancel.\n\n"
        msg += self.pprint_judging(judging)
        confirm_msg = await ctx.message.reply(msg)

        confirmed = await self.get_confirmation(ctx.message.author, confirm_msg)
        if confirmed == None:
            # timed out
            return
        elif confirmed == False:
            # reacted with ❌
            await confirm_msg.reply(f"Judging was not started.")
            return
        else:
            await confirm_msg.reply(f"Judging started! ✨")

        # otherwise, we are good to go with this judging
        self.judging = judging

        # send confirmation in judging log channel
        msg = "Started new judging scheme.\n"
        msg += self.pprint_judging(self.judging)
        await self.send_in_judging_log(ctx, msg)


    @commands.command(help=f'''Usage: `{config['prefix']}next <room_id>`.''')
    async def next(self, ctx, room_id: Optional[str]):

        if not check_author_perms(ctx):
            return

        # check arguments

        if room_id not in self.judging.keys():
            await ctx.message.add_reaction("❌")
            await ctx.reply(f"Queue was not moved; room ID {room_id} either does not exist or has no participants being judged in it.")
            return

        elif self.judging[room_id]["next_team"] > len(self.judging[room_id]["teams"]):
            await ctx.message.add_reaction("❌")
            await ctx.reply(f"Queue was not moved; there are no more participants to judge in this room.")
            return

        elif self.judging[room_id]["next_team"] == len(self.judging[room_id]["teams"]):
            # finished with this room
            await ctx.message.add_reaction("✅")
            await ctx.reply(f"All teams have now been judged for room `{room_id}`. ✨")
            self.judging[room_id]["next_team"] += 1

            # log change
            msg = f"All teams have now been judged for room `{room_id}`.\n"
            msg += self.pprint_judging(self.judging)
            await self.send_in_judging_log(ctx, msg)
            return
        
        # move queue along
        team_name = self.judging[room_id]["teams"][ self.judging[room_id]["next_team"] ]
        self.judging[room_id]["next_team"] += 1

        # ping the next group in judging ping channel

        channel = dget(ctx.message.guild.channels, id=config["judging_ping_channel_id"])
        team_role = dget(ctx.message.guild.roles, name=team_name)

        if config["judging_rooms"]["room_id"]["medium"] == "online":
            msg = f"Hey {team_role.mention}, you're up next for judging! You are being judged **online**. Please join {config['judging_rooms']['room_id']['waiting_vc']} as soon as possible."
        elif config["judging_rooms"]["room_id"]["medium"] == "inperson":
            msg = f"Hey {team_role.mention}, you're up next for judging! You are being judged **in-person**. Please report to the front desk as soon as possible, from where you will be directed to your judging room."

        await channel.send(msg) # send ping

        await ctx.message.add_reaction("✅") # react to original command
