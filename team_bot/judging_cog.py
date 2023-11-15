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

# lazy configuration for who's allowed to do what


class Judging(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.judging = {}

        self.judging_medium_msg = None
        self.judging_category_msg = None


    def gen_filename(self, tag, ext):
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        return data_dir / f"{tag}_{timestamp}.{ext}"


    async def send_as_json(self, ctx, dictionary, filename):
        # make file
        save_filename = self.gen_filename("generated", "json")
        with open(save_filename, "w") as f:
            f.write(json.dumps(dictionary, indent=4))

        # send file
        await ctx.send(file=discord.File(save_filename, filename=filename))


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

    
    async def get_judging_log(self, ctx):
        channel = dget(ctx.message.guild.channels, id=config['judging_log_channel_id']) # get log channel
        return channel
    

    @commands.command(help=f'''Sets the judging react messages that will be used if `auto_make_queue` is called. Restricted.
    Usage: {config['prefix']}set_judging_react_messages <#channel> <medium_message_id> <category_message_id>
    
    * medium_message_id   : the ID of the message where participants can react with {config['inperson_react']} for in-person judging, or {config['online_react']} for online judging.
    * category_message_id : the ID of the message where participants can react with one of {', '.join([info['react'] for cat, info in config['judging_categories'].items() if cat != 'default'])} for special judging categories.
    * channel             : the channel where both messages are located.''')
    async def set_judging_react_messages(self, ctx, channel: discord.TextChannel, medium_msg_id: str, category_msg_id: str):
        ''' Adds reactions to two messages to act as judging medium (online/inperson) and special categories reaction choice menus. '''

        if not utils.check_perms(ctx.message.author, config["perms"]["can_control_judging"]):
            logging.info(f"set_judging_react_messages: ignoring nonpermitted call by {ctx.message.author.name}")
            return
        
        logging.info(f"set_judging_react_messages: called with channel={channel}, medium_msg_id={medium_msg_id}, category_msg_id={category_msg_id}.")
        
        # verify both messages exist
        try:
            medium_msg = await channel.fetch_message(medium_msg_id)
            category_msg = await channel.fetch_message(category_msg_id)
        except:
            await ctx.message.add_reaction("❌")
            await ctx.reply("set_judging_react_messages: Messages were not set; one or both messages could not be found. Check the channel and IDs again.")

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

        logging.info(f"set_judging_react_messages: Set judging_medium_msg={self.judging_medium_msg}")
        logging.info(f"set_judging_react_messages: Set judging_category_msg={self.judging_category_msg}")
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


    @commands.command(help=f'''Automatically generate judging queues, based on the judging rooms defined in this bot's config and the reactions to the messages set using the `set_judging_react_messages` command. Restricted.
    Usage: {config['prefix']}auto_make_queues''')
    async def auto_make_queues(self, ctx):
        '''
        Automatically generate judging queues for judging rooms defined in config.json, based on the 
        reactions to self.judging_medium_msg and self.judging_category_msg.
        
        Requires `set_judging_react_messages` to have been run first.
        '''

        if not utils.check_perms(ctx.message.author, config["perms"]["can_control_judging"]):
            logging.info(f"auto_make_queues: ignoring nonpermitted call by {ctx.message.author.name}")
            return
        
        logging.info(f"auto_make_queues: called.")

        # check we have the messages necessary to make queues
        if self.judging_medium_msg == None or self.judging_category_msg == None:
            await ctx.message.add_reaction("❌")
            await ctx.reply("auto_make_queues: Judging medium and category messages haven't been set yet. Ensure you run `set_judging_react_messages` before this command.")

        # add special queue logger just for this <3
        root_logger = logging.getLogger()
        main_log_handler = root_logger.handlers[0]
        root_logger.removeHandler(main_log_handler) # remove the main log handler temporarily

        queue_log_name = self.gen_filename("autoqueue", ".txt")
        queue_log_handler = logging.FileHandler(queue_log_name)
        formatter = logging.Formatter('%(message)s')
        queue_log_handler.setFormatter(formatter)
        root_logger.addHandler(queue_log_handler)

        # get information from messages

        medium_icons = [config["inperson_react"], config["online_react"]]
        category_icons = [info["react"] for cat, info in config["judging_categories"].items() if cat != "default"]

        team_medium_reacts = await self.get_team_reacts(self.judging_medium_msg, accepted_icons=medium_icons)
        team_category_reacts = await self.get_team_reacts(self.judging_category_msg, accepted_icons=category_icons)

        logging.info("auto_make_queues: Reactions pulled from the judging messages, by-team:")
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
        logging.info("auto_make_queues: Finished auto-generating queue.")
        queue_log_handler.close()
        root_logger.removeHandler(queue_log_handler)
        root_logger.addHandler(main_log_handler)

        # send info message
        await ctx.reply("This is a json file mapping the *room ID* (as specified in the config.json for this bot) to a list of *team names* (as in the Discord roles), as well as a txt log file for the algorithm. Check the txt log file to make sure everything looks right, modify the json as desired, and then use the json to start judging with the `start_judging` command (be careful with that though).")

        # send generated queue
        await self.send_as_json(ctx, judging, filename="judging_breakdown.json")

        await ctx.send(file=discord.File(queue_log_name, filename="queue_log.txt"))


    @commands.command(help=f'''Starts the judging process using the contents of the json file attached. This will completely discard any judging process that is currently being run, and the bot will start off with the configuration described in the json. Restricted.
    Usage: {config['prefix']}start_judging
    (The message must have a json file attached with the judging breakdown, in the same format as the json output of `auto_make_queues`.)''')
    async def start_judging(self, ctx):

        if not utils.check_perms(ctx.message.author, config["perms"]["can_control_judging"]):
            logging.info(f"start_judging: ignoring nonpermitted call by {ctx.message.author.name}")
            return

        logging.info(f"start_judging: called.")

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
        filename = self.gen_filename("received", "json")
        
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
            logging.info("start_judging: Unable to read json.")

            await ctx.message.add_reaction("❌")
            await ctx.reply(f"Judging was not started; there's likely something wrong with your json. Make sure it matches the format of the output of `setup_queues`.\nError message: `{e}`")

        # get confirmation
        msg = "This is the judging scheme that you are about to switch to. Verify it is correct, and then react to this message with ✅ to confirm, or ❌ to cancel.\n\n"
        msg += self.pprint_judging(judging)
        confirm_msg = await ctx.message.reply(msg)
        confirmed = await utils.get_confirmation(self.bot, ctx.message.author, confirm_msg)

        if confirmed == None:
            # timed out
            return
        elif confirmed == False:
            # reacted with ❌
            await confirm_msg.reply(f"Judging was not started.")
            return
        
        # otherwise, we are good to go with this judging
        self.judging = judging
        await confirm_msg.reply(f"Judging started! ✨")

        # send confirmation in judging log channel
        msg = "Started new judging scheme.\n"
        msg += self.pprint_judging(self.judging)
        judging_log = await self.get_judging_log(ctx)
        await judging_log.send(msg)
        await self.send_as_json(judging_log, self.judging, filename="judging_breakdown.json")


    @commands.command(help=f'''Moves the judging queue along for the room associated with the text channel this command was run in (as described in the config). Restricted.
    Usage: {config['prefix']}next
    (Must be run in a text channel associated with a judging room.)''')
    async def next(self, ctx, room_id: str):

        if not utils.check_perms(ctx.message.author, config["perms"]["can_control_judging"]):
            logging.info(f"next: ignoring nonpermitted call by {ctx.message.author.name}")
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
            await self.send_as_json(judging_log, self.judging, filename="judging_breakdown.json")
            return
        
        elif self.judging[room_id]["next_team"] > len(self.judging[room_id]["teams"]):
            logging.info(f"next: `{room_id}` has no more participants to judge")
            await ctx.message.add_reaction("❌")
            await ctx.reply(f"Queue was not moved; there are no more participants to judge in this room.")
            return
        

        team_name = self.judging[room_id]["teams"][ self.judging[room_id]["next_team"] ]

        # get confirmation
        confirm_msg = await ctx.message.reply(f"The queue for room {room_id} will be incremented, meaning {team_name} will be next to be judged. React to this message with ✅ to confirm, or ❌ to cancel.")
        confirmed = await utils.get_confirmation(self.bot, ctx.message.author, confirm_msg)

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
        await self.send_as_json(judging_log, self.judging, filename="judging_breakdown.json")

        await ctx.message.add_reaction("✅") # react to original command

        await confirm_msg.reply(f"Queue was incremented, and `{team_name}` was pinged in {team_text.mention} and told to report to {team_location}.")


    @commands.command(help=f'''Moves all participants in the waiting VC to the judging VC, for waiting/judging rooms associated with the text channel this command was run in. Restricted.
    Usage: {config['prefix']}vcpull
    (Must be run in a text channel associated with a judging room.)''')
    async def vcpull(self, ctx):

        if not utils.check_perms(ctx.message.author, config["perms"]["can_vcpull"]):
            logging.info(f"vcpull: ignoring nonpermitted call by {ctx.message.author.name}")
            return
        
        logging.info(f"vcpull: run")

        # check channel
        cid = ctx.channel.id
        for room, info in config["judging_rooms"]:
            if "text" in info.keys() and info["text"] == cid:
                logging.info(f"vcpull: was run in channel for {room}")

                # command was run in the text channel for a particular room
                waiting_vc = dget(ctx.guild.channels, id=info["waiting_vc"])
                judging_vc = dget(ctx.guild.channels, id=info["waiting_vc"])

                # move everyone in the waiting_vc into the judging_vc
                print(waiting_vc.voice_states)

                for member in waiting_vc.voice_states.values():
                    await member.move_to(judging_vc)

                await ctx.message.add_reaction("✅") # react to original command
                break

        else:
            await ctx.message.add_reaction("❌") # react to original command
            await ctx.message.reply("Make sure you are running this command in the text channel associated with a judging room.")
