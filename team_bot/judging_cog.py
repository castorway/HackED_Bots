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


    def get_team_artefacts(self, ctx, team_name):
        try:
            logging.info(f"trying to get team artefacts for team={team_name}")
            team_cat = dget(ctx.message.guild.categories, name=team_name)
            logging.info(f"team_cat={team_cat}")

            team_text = [c for c in team_cat.channels if type(c) == discord.TextChannel][0]
            team_vc = [c for c in team_cat.channels if type(c) == discord.VoiceChannel][0]
            
            team_role = dget(ctx.message.guild.roles, name=team_name)

        except AttributeError as e:
            logging.error(f"couldn't find artefacts for team {team_name}.")
            return None

        return (team_role, team_cat, team_text, team_vc)


    def pprint_judging(self, judging=None):
        msg = "```md\n"
        msg += f"JUDGING\n"
        msg += f"==========================\n"
        msg += f"The team highlighted in <green> is the *current team* that is being judged (if any). The team after it is the team that will be pinged when `next <room_id>` is run.\n"

        if judging == None:
            judging = self.judging

        for room_id, info in judging.items():
            # room status
            if info['next_team'] == 0:
                status = "Not Started"
            elif info["next_team"] <= len(info["teams"]):
                status = "In Progress"
            else:
                status = "Done"
            
            msg += f"\n[{room_id}][{status}]\n"

            # print each team
            for i, team_name in enumerate(judging[room_id]["teams"]):
                if i < info["next_team"] - 1:
                    msg += f"- {team_name}\n"
                elif i == info["next_team"] - 1:
                    msg += f"> {team_name}\n"
                else:
                    msg += f"* {team_name}\n"
        
        msg += "```"
        
        return msg


    def my_log(self, log_file, txt):
        with open(log_file, "a") as f:
            f.write(txt + "\n")

    
    async def get_judging_log(self, ctx):
        channel = dget(ctx.message.guild.channels, id=config['judging_log_channel_id']) # get log channel
        return channel


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
        except:
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
            if config["online_react"] in team_medium_reacts[team_name]:
                team_medium_pref[team_name] = "online"
            elif config["inperson_react"] in team_medium_reacts[team_name]:
                team_medium_pref[team_name] = "inperson"
            else:
                team_medium_pref[team_name] = config["default_judging_medium_pref"]
            
            # get unique categories chosen
            if team_name in team_category_reacts.keys():
                team_category_choice[team_name] = [icon_to_category[e] for e in list(set(team_category_reacts[team_name]))]
            else:
                team_category_choice[team_name] = []

        # icon_to_category = {info["react"]: cat for cat, info in config["judging_categories"].items() if cat != "default"}

        # map choice of (category, medium) to teams
        room_dist = queue_algorithm(team_category_choice, team_medium_pref)

        # make formatted judging dict
        judging = {
            room_id: {
                "next_team": 0,
                "teams": room_dist[room_id]
            }
            for room_id in room_dist.keys()
        }
        
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
        judging_log = await self.get_judging_log(ctx)
        await judging_log.send(msg)
        await send_as_json(judging_log, self.judging, filename="judging_breakdown.json")


    @commands.command(help=f'''Usage: `{config['prefix']}next <room_id>`.''')
    async def next(self, ctx, room_id: str):

        if not check_author_perms(ctx):
            return
        
        logging.info(f"next: run with room_id={room_id}")

        # check arguments

        if room_id not in self.judging.keys():
            logging.info(f"next: room {room_id} not found in judging rooms {list(self.judging.keys())}, exiting")
            await ctx.message.add_reaction("❌")
            await ctx.reply(f"Queue was not moved; room ID `{room_id}` either does not exist or has no participants being judged in it.")
            return

        elif self.judging[room_id]["next_team"] == len(self.judging[room_id]["teams"]):
            # this is being run just after the final team is judged
            logging.info(f"next: final team just judged in `{room_id}`, removing their permissions and updating log")

            # remove prev team's permissions
            if self.judging[room_id]["next_team"] > 0:
                waiting_vc = dget(ctx.message.guild.channels, id=config["judging_rooms"][room_id]["waiting_vc"])
                prev_team = self.judging[room_id]["teams"][ self.judging[room_id]["next_team"] - 1 ]

                # get the previous team and remove their permissions, if there was one
                ret = self.get_team_artefacts(ctx, prev_team)
                if ret != None:
                    prev_role, prev_cat, prev_text, prev_vc = ret
                    await waiting_vc.set_permissions(prev_role, read_messages=False) # prev team can't view waiting room
                else:
                    logging.error(f"next: unable to remove permissions for team `{prev_team}` because their artefacts could not be found")
            
            self.judging[room_id]["next_team"] += 1

            # finished with this room
            await ctx.message.add_reaction("✅")
            await ctx.reply(f"All teams have now been judged for room `{room_id}`. ✨")

            # log change
            judging_log = await self.get_judging_log(ctx)
            msg = f"All teams have now been judged for room `{room_id}`."
            msg += self.pprint_judging(self.judging)

            await judging_log.send(msg)
            await send_as_json(judging_log, self.judging, filename="judging_breakdown.json")
            return
        
        elif self.judging[room_id]["next_team"] > len(self.judging[room_id]["teams"]):
            logging.info(f"next: `{room_id}` has no more participants to judge")
            await ctx.message.add_reaction("❌")
            await ctx.reply(f"Queue was not moved; there are no more participants to judge in this room.")
            return
        

        team_name = self.judging[room_id]["teams"][ self.judging[room_id]["next_team"] ]

        # get confirmation
        confirm_msg = await ctx.message.reply(f"The queue for room {room_id} will be incremented, meaning {team_name} will be next to be judged. React to this message with ✅ to confirm, or ❌ to cancel.")
        await confirm_msg.add_reaction("✅")
        await confirm_msg.add_reaction("❌")
        confirmed = await self.get_confirmation(ctx.message.author, confirm_msg)

        if confirmed == None:
            # timed out
            return
        elif confirmed == False:
            # reacted with ❌
            await confirm_msg.reply(f"Queue was not incremented.")
            return
        
        # else confirmed == True, continue with code

        # flag so we know if we need to remove prev team's permissions
        if self.judging[room_id]["next_team"] > 0:
            prev_team = self.judging[room_id]["teams"][ self.judging[room_id]["next_team"] - 1 ]
        else:
            prev_team = None

        # get the team role and text channel. text channels have weird name restrictions so you need to get the
        # category and then get the channel from that
        ret = self.get_team_artefacts(ctx, team_name)

        if ret == None:
            logging.error(f"couldn't get artefacts for `{team_name}`")
            await ctx.message.add_reaction("❌")
            await ctx.reply(f"There was an issue getting the category or role for this team; you need to handle pinging and VC permissions manually for them.")
            return
        
        team_role, team_cat, team_text, team_vc = ret

        if config["judging_rooms"][room_id]["medium"] == "online":
            
            # we also need to give the team access to the waiting room
            waiting_vc = dget(ctx.message.guild.channels, id=config["judging_rooms"][room_id]["waiting_vc"])
            await waiting_vc.set_permissions(team_role, read_messages=True) # team can view waiting room

            # get the previous team and remove their permissions, if there was one
            if prev_team != None:
                logging.info(f"next: removing prev team `{prev_team}`'s permissions")
                ret = self.get_team_artefacts(ctx, prev_team)
                if ret != None:
                    prev_role, prev_cat, prev_text, prev_vc = ret
                    await waiting_vc.set_permissions(prev_role, read_messages=False) # prev team can't view waiting room
                else:
                    logging.error(f"unable to remove permissions for team `{prev_team}` because their artefacts could not be found")

            await team_text.send(f"Hey {team_role.mention}, you're up next for judging! You are being judged **online**. Please join {waiting_vc.mention} as soon as possible.")
            team_location = waiting_vc.mention

        elif config["judging_rooms"][room_id]["medium"] == "inperson":
            await team_text.send(f"Hey {team_role.mention}, you're up next for judging! You are being judged **in-person**. Please report to the front desk as soon as possible, from where you will be directed to your judging room.")
            team_location = "front desk"

        else:
            raise ValueError(f"config has invalid medium for `{room_id}`")

        # move queue along
        self.judging[room_id]["next_team"] += 1

        # log progress and send new json
        judging_log = await self.get_judging_log(ctx)
        msg = f"Moved queue along for room `{room_id}`; currently `{team_name}` is being judged.\n"
        msg += self.pprint_judging(self.judging)

        await judging_log.send(msg)
        await send_as_json(judging_log, self.judging, filename="judging_breakdown.json")

        await ctx.message.add_reaction("✅") # react to original command

        await confirm_msg.reply(f"Queue was incremented, and `{team_name}` was pinged in {team_text.mention} and told to report to {team_location}.")


    @commands.command(help=f'''Usage: `{config['prefix']}vcpull`.''')
    async def vcpull(self, ctx):

        if not check_author_perms(ctx):
            return
        
        logging.info(f"vcpull: run")

        # check channel

       