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
import queuing
from copy import deepcopy
import database
from time import time

args, config = utils.general_setup()


class Judging(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.judging = {}

        self.judging_medium_msg = None
        self.judging_category_msg = None


    def now(self, code="T"):
        return f"<t:{int(time())}:{code}>"


    async def send_as_json(self, ctx, dictionary, filename):
        await utils.send_as_json(ctx, dictionary, save_with_tag="autoqueue", send_with_name=filename)


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


    def pprint_judging(self, judging=None, public=False, use_room_id=None):
        msg = f"# Judging\n"
        # using :scales: instead of emoji bc discord converts emoji to scales character
        if public:
            msg += f"The team indicated by :scales: is the current team being judged (if any). If you are one of the next few teams, we encourage you to report to the front desk (for in-person team members) or your team VC (for online team members) in advance.\n\n"
        else:
            msg += f"The team indicated by :scales: is the current team being judged (if any). The team after it is the team that will be pinged when `~ping <room_id>` is run.\n\n"

        if judging == None:
            judging = self.judging

        if use_room_id != None:
            # print info for just a single room
            use_rooms = [use_room_id]
        else:
            use_rooms = judging.keys()

        for room_id in use_rooms:
            info = judging[room_id]

            # room status
            if info["current"] < 0:
                status = "Not Started"
            elif info["current"] < len(info["teams"]):
                status = "In Progress"
            else:
                status = "Done"
            
            room_display_name = config["judging_rooms"][room_id]['display_name']
            if public:
                msg += f"### {room_display_name} `[{status}]`\n"
            else:
                msg += f"### {room_display_name}\n`[id = {room_id} | {status} | current = {info['current']}]`\n"

            # print each team
            for i in range(len(info["teams"])):
                team_name = info["teams"][i]

                if i < info["current"]:
                    msg += f"- `{team_name}` :white_check_mark:\n"
                elif i == info["current"]:
                    msg += f"- `{team_name}` :scales:\n"
                else:
                    msg += f"- `{team_name}`\n"
                
        return msg

    
    async def get_judging_log(self, ctx):
        channel = dget(ctx.message.guild.channels, id=config['private_judging_log_channel_id']) # get log channel
        return channel

    
    async def update_public_judging_log(self, ctx):
        '''
        Sends the current judging log to a public channel.
        '''
        channel = dget(ctx.message.guild.channels, id=config['public_judging_log_channel_id']) # get log channel
        await channel.send(self.pprint_judging(public=True))

    
    async def set_team_timer(self, ctx, room_id):
        '''
        Starts a timer to repeatedly pester the bot controller when a team should be pinged. Assumes this command is
        run right when the team starts presenting.

        Not used; easier to make timer the responsibility of the people in the room.
        '''
        controller = dget(ctx.guild.members, id=config["controller_id"])
        room_channel = dget(ctx.guild.channels, id=config["judging_rooms"][room_id]["text"])
        team_name = self.judging[room_id]["teams"][ self.judging[room_id]["current"] ]
        
        await room_channel.send(f"{controller.mention}, a timer has been started assuming `{team_name}` has just started presenting. Ping the next team so they are ready once `{team_name}` is done.")
        
        await asyncio.sleep(60 * 2) # ping them again after 2m

        # if something changed, leave
        if self.judging[room_id]["teams"][ self.judging[room_id]["current"] ] != team_name:
            logging.info(f"team_timer: left because team `{team_name}` no longer being judged")
            return
        await room_channel.send(f"{controller.mention}, it's been **2** minutes since `{team_name}` started presenting. Ping the next team again so they are ready once `{team_name}` is done.")

        await asyncio.sleep(60 * 2) # after 4m, ping both them and the team after them

        # if something changed, leave
        if self.judging[room_id]["teams"][ self.judging[room_id]["current"] ] != team_name:
            logging.info(f"team_timer: left because team `{team_name}` no longer being judged")
            return
        await room_channel.send(f"{controller.mention}, it's been **4** minutes since `{team_name}` started presenting.\nIf the next team isn't ready, ping both them and the team after.")

        await asyncio.sleep(60 * 1) # after 5m, allotted time is up

        if self.judging[room_id]["teams"][ self.judging[room_id]["current"] ] != team_name:
            logging.info(f"team_timer: left because team `{team_name}` no longer being judged")
            return
        await room_channel.send(f"{controller.mention}, it's been **5** minutes since `{team_name}` started presenting, which means their time is up.\nWrap up the presentation, and if there's a team ready to go then send them in.")
    

    @commands.command(help=f'''Automatically generate judging queues, based on the judging rooms defined in this bot's config and the reactions to the messages set using the `set_judging_react_messages` command. Restricted.
    
    Usage: {config['prefix']}make_template_queues <algorithm>
    * algorithm : first_chal_match
    ''')
    async def make_template_queues(self, ctx, algorithm: str):
        '''
        Automatically generate judging queues for judging rooms defined in config.json, based on the 
        reactions to messsages optionally provided.
        '''

        if not utils.check_perms(ctx.message.author, config["perms"]["can_control_judging"]):
            logging.info(f"make_template_queues: ignoring nonpermitted call by {ctx.message.author.name}")
            return
        
        logging.info(f"make_template_queues: called with algorithm {algorithm}.")

        # add special queue logger just for this <3
        root_logger = logging.getLogger()
        main_log_handler = root_logger.handlers[0]

        queue_log_name = utils.gen_filename("autoqueue_log", ".txt")
        queue_log_handler = logging.FileHandler(queue_log_name)
        formatter = logging.Formatter('%(message)s')
        queue_log_handler.setFormatter(formatter)

        root_logger.removeHandler(main_log_handler) # remove the main log handler temporarily
        root_logger.addHandler(queue_log_handler) # add a new handler

        try:

            # different algorithms use different information
            if algorithm == "first_chal_match":
                # get all the teams/challenge info from db
                rooms, unchosen, unassigned = queuing.first_chal_match()

                # make formatted judging dict
                judging = {
                    room_id: {
                        "teams": rooms[room_id],
                        "current": -1
                    }
                    for room_id in rooms.keys()
                }

                # info about teams that didnt sign up
                if unchosen:
                    st = '\n'.join([f"- `{team_name}`" for team_name in unchosen])
                    await ctx.reply("Teams that did not sign up for judging:\n" + st)
                else:
                    await ctx.reply("All teams have signed up for judging.")

                # info about teams that didnt get assigned a room
                if unassigned:
                    st = '\n'.join([f"- `{team_name}`" for team_name in unassigned])
                    await ctx.reply("Teams that signed up for judging but the algorithm did not assign to a room (**these teams must be manually given a room**):\n" + st)
                else:
                    await ctx.reply("All teams that signed up for judging were successfully assigned a room.")

                # send info message
                await ctx.reply("- `algorithm.log` is a log file for the algorithm used to sort teams into rooms.\n- `judging.json` is a template file to be used to start judging.\nCheck the log and previous messages to ensure all teams were assigned correctly (look for error messages), then modify the template file if necessary and use it to start judging with the `start_judging` command (be careful with that though).")

                await ctx.send(file=discord.File(queue_log_name, filename="algorithm.log"))
                await utils.send_as_json(ctx, judging, save_with_tag="autoqueue", send_with_name="judging.json")

            else:
                await ctx.message.add_reaction("❌")
                await ctx.reply("The only algorithms supported right now are: `first_chal_match`")
                return


        except Exception as e:
            # catching arbitrary exception despite bad practice because log handler still needs to be added back
            # if something goes wrong
            logging.error(f"something went wrong in the queuing!", exc_info=e)
            await ctx.message.add_reaction("❌")
            await ctx.reply(f"Something went wrong; check the bot logs.")
        
        # remove special queue logger
        logging.info("make_template_queues: Finished auto-generating queue.")
        queue_log_handler.close()
        root_logger.removeHandler(queue_log_handler)
        root_logger.addHandler(main_log_handler)


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
            await ctx.reply("Judging was not started; this command must be called with no arguments and exactly one attachment (a json in the same format output by `make_template_queues`).")

        # download the attachment
        # im no security expert but i could see this being a bit of a hazard. please do not hack my bot
        filename = utils.gen_filename("received", "json")
        with open(filename, "wb") as f:
            await ctx.message.attachments[0].save(fp=f)

        # validate file
        try:
            with open(filename, "r") as f:
                judging = json.loads(f.read())

            # get all teams for validation purposes
            teams_info = database.get_all_challenge_info()
            team_names = [team['team_name'] for team in teams_info]

            # some lazy validation. can't really check every possible issue here.
            for room_id in judging.keys():
                assert room_id in list(config["judging_rooms"].keys()), f"room id {room_id} not in config"
                assert -1 <= judging[room_id]["current"], f"for room id {room_id}, current team {judging[room_id]['current']} is invalid"

                if len(judging[room_id]["teams"]) > 0:
                    assert judging[room_id]["current"] <= len(judging[room_id]["teams"]), f"for room id {room_id}, current {judging[room_id]['current']} is invalid"
                
                for name in judging[room_id]["teams"]:
                    assert name in team_names, f"team name {name} in room id {room_id} does not exist"

        except (ValueError, AssertionError, KeyError) as e:
            # catch any issues, log them, and send to user
            logging.error(e)
            logging.info("start_judging: Unable to read json.")

            await ctx.message.add_reaction("❌")
            await ctx.reply(f"Judging was not started; there's likely something wrong with your json. Make sure it matches the format of the output of `make_template_queues`.\nError message: `{e}`")

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

        await self.update_public_judging_log(ctx) # and in public judging log


    @commands.command(help=f'''Pings the next team to be judged in a particular room. Restricted.
                      
    Usage: {config['prefix']}ping <room_id>
    Usage: {config['prefix']}ping <room_id> <team_name>
    
    (The command must be run in the text channel matching <room_id>.)''')
    async def ping(self, ctx, room_id: str, team_name: Optional[str]):

        # check permissions
        if not utils.check_perms(ctx.message.author, config["perms"]["can_control_judging"]):
            logging.info(f"ping: ignoring nonpermitted call by {ctx.message.author.name}")
            return
        
        # check room_id matches text channel run in
        if room_id not in self.judging.keys():
            logging.info(f"ping: room {room_id} not found in judging rooms {list(self.judging.keys())}, exiting")
            await ctx.message.add_reaction("❌")
            await ctx.reply(f"Team was not pinged; room ID `{room_id}` either does not exist or has no participants being judged in it.")
            return
        elif config["judging_rooms"][room_id]["text"] != ctx.channel.id:
            logging.info(f"ping: room {room_id} doesn't match channel `{ctx.channel.name}`, exiting")
            await ctx.message.add_reaction("❌")
            await ctx.reply(f"Team was not pinged; room ID `{room_id}` does not match the channel this command was run in. Ensure you run this command in the text channel associated with the judging room `{room_id}`.")
            return
        
        logging.info(f"ping: run with room_id={room_id}")

        if team_name == None:
            # check special cases where there is no team to ping
            if self.judging[room_id]["current"] == len(self.judging[room_id]["teams"]) - 1:
                # this is being run while the current team being judged is last in the queue
                logging.info(f"ping: run while final team being judged, not pinging anyone")
                await ctx.message.add_reaction("❌")
                await ctx.reply(f"Team was not pinged; the current team being judged is the final team in the queue.")
                return
            elif self.judging[room_id]["current"] > len(self.judging[room_id]["teams"]) - 1:
                # this is being run after all teams have been judged
                logging.info(f"ping: run once queue over, not pinging anyone")
                await ctx.message.add_reaction("❌")
                await ctx.reply(f"Team was not pinged; judging has finished for this room.")
                return
        
            # otherwise, this is being run while a team that is not last in the queue is being judged (or no team is being judged, i.e. current == -1)
            # so we want to ping the team that comes after them

            next_team_idx = self.judging[room_id]["current"] + 1
            team_name = self.judging[room_id]["teams"][next_team_idx]

            explain_msg = f"Team `{team_name}` is next in line for room `{room_id}` and will be pinged"

        else:
            explain_msg = f"Team `{team_name}` will be pinged"

        # get confirmation
        confirm_msg = await ctx.message.reply(f"{explain_msg}. ✅/❌?")
        confirmed = await utils.get_confirmation(self.bot, ctx.message.author, confirm_msg)
        if confirmed == None: # timed out
            return
        elif confirmed == False: # reacted with ❌
            await confirm_msg.reply(f"Team was not pinged.")
            return

        # get the team role and text channel. text channels have weird name restrictions so you need to get the
        # category and then get the channel from that
        ret = database.get_team_info(ctx.guild, team_name)
        if any([ret[v] == None for v in ['team_text', 'team_vc', 'team_cat', 'team_role']]):
            logging.error(f"couldn't get an item for `{team_name}`: {ret}")
            await ctx.message.add_reaction("❌")
            await ctx.reply(f"There was an issue getting the category or role for this team; you will need to handle them manually.")
            return
        
        team_role = ret['team_role']
        team_cat = ret['team_cat']
        team_text = ret['team_text']
        team_vc = ret['team_vc']
        
        # actually ping the team, and send instructions to involved humans
        if config["judging_rooms"][room_id]["mediums"] == ["online"]:
            await team_text.send(f"Hey {team_role.mention}, you're up next for judging! You are being judged **online**. Please join {team_vc.mention} as soon as possible, and when the judges are ready you will be moved to the judging room.")
        
        elif config["judging_rooms"][room_id]["mediums"] == ["in-person"]:
            await team_text.send(f"Hey {team_role.mention}, you're up next for judging! You are being judged **in-person**. Please report to the front desk as soon as possible, from where you will be directed to your judging room.")
        
        else:
            # hybrid room; this is all rooms atm
            await team_text.send(f"Hey {team_role.mention}, you're up next for judging!\n- For in-person team members: please report to the front desk as soon as possible, from where you will be directed to your judging room.\n- For online team members: please join {team_vc.mention} as soon as possible, and when the judges are ready you will be moved to the judging room.")
        
        # send confirmation
        # await ctx.message.add_reaction("✅") # react to original command
        await ctx.message.reply(f"[{self.now()}] `{team_name}` was pinged in {team_text.mention}.")


    @commands.command(help=f'''Moves the judging queue along for the room named `room_id` in the config. To be run once a team has been sent in. Restricted.
                      
    Usage: {config['prefix']}tick <room_id>''')
    async def tick(self, ctx, room_id: str):

        # check permissions
        if not utils.check_perms(ctx.message.author, config["perms"]["can_control_judging"]):
            logging.info(f"tick: ignoring nonpermitted call by {ctx.message.author.name}")
            return
        
        # check room_id matches text channel run in
        if room_id not in self.judging.keys():
            logging.info(f"tick: room {room_id} not found in judging rooms {list(self.judging.keys())}, exiting")
            await ctx.message.add_reaction("❌")
            await ctx.reply(f"Queue was not moved; room ID `{room_id}` either does not exist or has no participants being judged in it.")
            return
        elif config["judging_rooms"][room_id]["text"] != ctx.channel.id:
            logging.info(f"tick: room {room_id} doesn't match channel `{ctx.channel.name}`, exiting")
            await ctx.message.add_reaction("❌")
            await ctx.reply(f"Queue was not moved; room ID `{room_id}` does not match the channel this command was run in. Ensure you run this command in the text channel associated with the judging room `{room_id}`.")
            return
        
        logging.info(f"tick: run with room_id={room_id}")

        # check special cases where we can't move queue
        if self.judging[room_id]["current"] == len(self.judging[room_id]["teams"]) - 1:
            # this is being run while the final team is being judged
            logging.info(f"tick: final team is being judged in `{room_id}`, updating log")
            
            self.judging[room_id]["current"] += 1 # current = len(teams) + 1

            # finished with this room
            await ctx.message.add_reaction("✅")
            await ctx.reply(f"All teams have now been judged for room `{room_id}`. ✨")

            # log change
            judging_log = await self.get_judging_log(ctx)
            msg = f"All teams have now been judged for room `{room_id}`."
            msg += self.pprint_judging(self.judging)

            await judging_log.send(msg)
            await self.send_as_json(judging_log, self.judging, filename="judging_breakdown.json")

            await self.update_public_judging_log(ctx)
            return
        
        elif self.judging[room_id]["current"] > len(self.judging[room_id]["teams"]) - 1:
            # this is being run after `tick` already run for final team
            logging.info(f"tick: `{room_id}` has no more participants to judge")
            await ctx.message.add_reaction("❌")
            await ctx.reply(f"Queue was not moved; there are no more participants to judge in this room.")
            return
        
        # otherwise, this is being run while a team before the final team is being judged. we need to increment the queue
        # such that 'current team' reflects the team currently being judged in the room, and 'next team' is the team that
        # we want to start pinging with `ping`.

        team_idx = self.judging[room_id]["current"]
        
        if team_idx == -1: 
            # judging just started, no team is current yet
            team_name = None
            next_team_name = self.judging[room_id]["teams"][0]
            explain_msg = f"no team has been judged yet, and `{next_team_name}` is going in to be judged"
        else:
            team_name = self.judging[room_id]["teams"][team_idx]
            next_team_name = self.judging[room_id]["teams"][team_idx + 1]
            explain_msg = f"`{team_name}` has finished being judged, and `{next_team_name}` is going in to be judged"

        # get confirmation
        confirm_msg = await ctx.message.reply(f"The queue for room `{room_id}` will be moved. This means that {explain_msg}. ✅/❌?")
        confirmed = await utils.get_confirmation(self.bot, ctx.message.author, confirm_msg)
        if confirmed == None: # timed out
            return
        elif confirmed == False: # reacted with ❌
            await confirm_msg.reply(f"Queue was not moved.")
            return
        
        # else confirmed == True, move queue along
        self.judging[room_id]["current"] += 1

        # get this judging channel
        judging_vc = dget(ctx.guild.channels, id=config['judging_rooms'][room_id]['judging_vc'])

        # send info to people in judging room
        pretty_text = dget(ctx.guild.channels, id=config['judging_rooms'][room_id]['pretty'])
        if pretty_text == None:
            logging.warning(f"Couldn't find pretty/judge-visible logging channel for {room_id}")
        else:
            # construct info about team to send to judges
            msg = database.get_team_display(ctx, next_team_name)
            info_msg = await pretty_text.send(f"This team is:\n" + msg + '\n')
            await info_msg.edit(suppress=True) # remove embeds

        # log progress and send new json
        judging_log = await self.get_judging_log(ctx)
        msg = f"Moved queue along for room `{room_id}`; {explain_msg}.\n"
        msg += self.pprint_judging(self.judging)

        await judging_log.send(msg)
        await self.send_as_json(judging_log, self.judging, filename="judging_breakdown.json")

        # await ctx.message.add_reaction("✅") # react to original command
        await confirm_msg.reply(f"[{self.now()}] Queue was moved. This means that {explain_msg}.")

        await self.update_public_judging_log(ctx)
        # await self.set_team_timer(ctx, room_id)

    
    @commands.command(help=f'''Skips the 'next team' in the judging queue for this room and shunts them to the end of the queue. The 'current team' remains unchanged. Restricted.
                      
    Usage: {config['prefix']}skip <room_id>''')
    async def skip(self, ctx, room_id: str):

        # check permissions
        if not utils.check_perms(ctx.message.author, config["perms"]["can_control_judging"]):
            logging.info(f"skip: ignoring nonpermitted call by {ctx.message.author.name}")
            return
        
        # check room_id matches text channel run in
        if room_id not in self.judging.keys():
            logging.info(f"skip: room {room_id} not found in judging rooms {list(self.judging.keys())}, exiting")
            await ctx.message.add_reaction("❌")
            await ctx.reply(f"Queue was not moved; room ID `{room_id}` either does not exist or has no participants being judged in it.")
            return
        elif config["judging_rooms"][room_id]["text"] != ctx.channel.id:
            logging.info(f"skip: room {room_id} doesn't match channel `{ctx.channel.name}`, exiting")
            await ctx.message.add_reaction("❌")
            await ctx.reply(f"Queue was not moved; room ID `{room_id}` does not match the channel this command was run in. Ensure you run this command in the text channel associated with the judging room `{room_id}`.")
            return
        
        logging.info(f"skip: run with room_id={room_id}")

        # check special cases where we cannot skip
        if self.judging[room_id]["current"] + 1 == len(self.judging[room_id]["teams"]):
            # no reason to skip the final team! it will just like add them back to the end which makes no sense
            logging.info(f"skip: tried to skip final team in `{room_id}`, exiting")
            await ctx.message.add_reaction("❌")
            await ctx.reply(f"Running `skip` when the queue is at the final team doesn't make sense, they will just be added back to the queue in the same position! Use `next` if you want to clear this team from the queue without judging them.")
            return
        
        elif self.judging[room_id]["current"] + 1 > len(self.judging[room_id]["teams"]):
            # this is being run after all teams judged, there is nobody to skip
            logging.info(f"tick: `{room_id}` has no more participants to judge")
            await ctx.message.add_reaction("❌")
            await ctx.reply(f"Queue was not moved; there are no more participants to judge in this room, so there is nobody to skip.")
            return
        
        # otherwise, this is being run while a team before the final team is being judged. we will modify
        # the queue so that 'current team' remains the same team, but 'current team + 1' now refers to the team after
        # this team, and appent this team to the end of the queue for later.

        skip_team_idx = self.judging[room_id]["current"] + 1 # index of team to skip (next team)
        skip_team_name = self.judging[room_id]["teams"][skip_team_idx]

        # i know this is inefficient, this bot doesn't need to be running at maximum efficiency tbh
        new_queue = deepcopy(self.judging[room_id]["teams"][:skip_team_idx]) \
                    + deepcopy(self.judging[room_id]["teams"][skip_team_idx+1:]) \
                    + [ self.judging[room_id]["teams"][skip_team_idx] ]

        # new_extra = deepcopy(self.judging[room_id]["extra"][:skip_team_idx]) \
        #             + deepcopy(self.judging[room_id]["extra"][skip_team_idx+1:]) \
        #             + [ self.judging[room_id]["extra"][skip_team_idx] + " (skipped)" ]

        mock_judging = deepcopy(self.judging)
        mock_judging[room_id]["teams"] = new_queue
        # mock_judging[room_id]["extra"] = new_extra

        # get confirmation
        msg = f"Team `{skip_team_name}` will be skipped and appended to the end of the queue. The team will be notified that they have been skipped. The new queue will look like this:\n"
        msg += self.pprint_judging(mock_judging, use_room_id=room_id)
        msg += "\nDo you still want to skip this team ✅/❌?"

        confirm_msg = await ctx.message.reply(msg)
        confirmed = await utils.get_confirmation(self.bot, ctx.message.author, confirm_msg)
        if confirmed == None: # timed out
            return
        elif confirmed == False: # reacted with ❌
            await confirm_msg.reply(f"Team was not skipped.")
            return
        
        # else confirmed == True, continue with skipping team
        self.judging = mock_judging

        # send new json
        judging_log = await self.get_judging_log(ctx)
        msg = f"Skipped team `{skip_team_name}` in room `{room_id}` and appended them to end of queue.\n"
        msg += self.pprint_judging(self.judging, use_room_id=room_id)

        await judging_log.send(msg)
        await self.send_as_json(judging_log, self.judging, filename="judging_breakdown.json")

        # notify skipped team they have been skipped

        # get the team role and text channel        
        ret = database.get_team_info(ctx.guild, skip_team_name)
        if any([ret[v] == None for v in ['team_text', 'team_vc', 'team_cat', 'team_role']]):
            logging.error(f"couldn't get an item for `{skip_team_name}`: {ret}")
            await ctx.message.add_reaction("❌")
            await ctx.reply(f"There was an issue getting the category or role for this team; you will need to handle them manually. **They have still been skipped; be careful!**")
        
        team_role = ret['team_role']
        team_cat = ret['team_cat']
        team_text = ret['team_text']
        team_vc = ret['team_vc']

        await team_text.send(f"{team_role.mention} We didn't see you report for judging, so we've skipped your team for now and moved you down in our judging queue. If you don't make it when pinged again for your second call time, we will have to exclude your project from judging.")

        await ctx.message.add_reaction("✅") # react to original command
        await ctx.message.reply(f"Team {skip_team_name} was skipped.")

        await self.update_public_judging_log(ctx)


    @commands.command(help=f'''Moves all participants in the waiting VC to the judging VC, for waiting/judging rooms associated with the text channel this command was run in. Also removes access to VC for all other teams, and gives access to this team. Restricted.
    
    Usage: {config['prefix']}vcpull <room_id>
    Usage: {config['prefix']}vcpull <room_id> <team_name>

    * room_id : The room whose associated judging VC you want to pull the team into.
    * team_name (optional) : The name of the team. If not specified, you will pull the 'next up' team.

    (Must be run in a text channel associated with a judging room.)''')
    async def vcpull(self, ctx, room_id: str, team_name: Optional[str]):

        # check permissions
        if not utils.check_perms(ctx.message.author, config["perms"]["can_vcpull"]):
            logging.info(f"vcpull: ignoring nonpermitted call by {ctx.message.author.name}")
            return
        
        # check room_id matches text channel run in
        # use config["judging_rooms"] instead of self.judging because maybe we want to use this as a utility in general
        if room_id not in config["judging_rooms"].keys():
            logging.info(f"vcpull: room {room_id} not found in judging rooms {list(config['judging_rooms'].keys())}, exiting")
            await ctx.message.add_reaction("❌")
            await ctx.reply(f"No participants were moved; room ID `{room_id}` either does not exist or has no participants being judged in it.")
            return
        elif config["judging_rooms"][room_id]["text"] != ctx.channel.id:
            logging.info(f"vcpull: room {room_id} doesn't match channel `{ctx.channel.name}`, exiting")
            await ctx.message.add_reaction("❌")
            await ctx.reply(f"No participants were moved; room ID `{room_id}` does not match the channel this command was run in. Ensure you run this command in the text channel associated with the judging room `{room_id}`.")
            return
        
        logging.info(f"vcpull: called with room_id {room_id}")

        # check special cases
        if team_name == None:
            if self.judging == {}:
                await ctx.message.add_reaction("❌") # react to original command
                await ctx.message.reply("You haven't specified a team, and there is no 'next team' in the judging queue because judging has not been started. Try specifying a team name.")
                return
            elif self.judging[room_id]["current"] + 1 == len(self.judging[room_id]["teams"]):
                # this was called when the final team is already being judged, there is no next team to pull
                await ctx.message.add_reaction("❌") # react to original command
                await ctx.message.reply("There is no next team to pull into the VC. Make sure you specify the team name if you meant to pull a different team; run `~help vcpull` for more information.")
                return
            else:
                # if a team name was specified, pull from their vc into the judging vc. if not, pull the next-up team (current + 1),
                # because next-up team hasn't started presenting yet so they aren't in the vc yet
                next_team_idx = self.judging[room_id]["current"] + 1
                team_name = self.judging[room_id]["teams"][next_team_idx]

        ret = self.get_team_artefacts(ctx, team_name)
        if ret == None:
            logging.error(f"couldn't get artefacts for `{team_name}`")
            await ctx.message.add_reaction("❌")
            await ctx.reply(f"There was an issue getting the category or role for this team; you will need to handle them manually.")
            return

        ret = database.get_team_info(ctx.guild, team_name)
        if any([ret[v] == None for v in ['team_text', 'team_vc', 'team_cat', 'team_role']]):
            logging.error(f"couldn't get an item for `{next_team_name}`: {ret}")
            await ctx.message.add_reaction("❌")
            await ctx.reply(f"There was an issue getting the category or role for team {ret}; you will need to handle them manually.")
        # team_role, team_cat, team_text, team_vc = ret

        judging_vc = dget(ctx.guild.channels, id=config["judging_rooms"][room_id]["judging_vc"])

        member_ids = ret['team_vc'].voice_states.keys() # people in the team vc

        # get confirmation
        confirm_msg = await ctx.reply(f"There are {len(member_ids)} users in {ret['team_vc'].mention} right now who will be moved into {judging_vc.mention}. `{team_name}` will be given access to {judging_vc.mention}, all other teams will have it revoked. ✅/❌?")
        confirmed = await utils.get_confirmation(self.bot, ctx.message.author, confirm_msg)
        if confirmed == None: # timed out
            return
        elif confirmed == False: # reacted with ❌
            await confirm_msg.reply("Participants were not moved.")
            return

        # revoke permissions from all other teams to enter room
        all_team_role_ids = database.get_all_team_role_ids()
        logging.info(all_team_role_ids)
        for member_or_role, overwrite in judging_vc.overwrites.items():
            if str(member_or_role.id) in all_team_role_ids:
                # remove overwrite
                logging.info(f"removing VC perms from @{member_or_role}")
                await judging_vc.set_permissions(dget(ctx.guild.roles, id=member_or_role.id), overwrite=None)

        # give permissions to this team to enter room
        await judging_vc.set_permissions(ret['team_role'], view_channel=True)

        # move everyone into the judging_vc
        for member_id in member_ids:
            member = dget(ctx.guild.members, id=member_id)
            await member.move_to(judging_vc)

        await ctx.message.add_reaction("✅") # react to original command


    @commands.command(help=f'''Quickly prints the judging queue. Restricted.
    
    Usage: {config['prefix']}q''')
    async def q(self, ctx, room_id: Optional[str]):
        '''
        This is mostly here as a fast shortcut-ish command to be run when you don't want to switch to the private judging
        log channel. Because you're either incredibly paranoid or just a hardcore gamer.
        '''

        # check permissions
        if not utils.check_perms(ctx.message.author, config["perms"]["can_control_judging"]):
            logging.info(f"q: ignoring nonpermitted call by {ctx.message.author.name}")
            return
        
        if room_id == None:
            await ctx.send(self.pprint_judging(use_room_id=room_id))
            return
        
        # otherwise, check room_id matches text channel run in
        if room_id not in self.judging.keys():
            logging.info(f"skip: room {room_id} not found in judging rooms {list(self.judging.keys())}, exiting")
            await ctx.message.add_reaction("❌")
            await ctx.reply(f"Queue was not moved; room ID `{room_id}` either does not exist or has no participants being judged in it.")
            return
        elif config["judging_rooms"][room_id]["text"] != ctx.channel.id:
            logging.info(f"skip: room {room_id} doesn't match channel `{ctx.channel.name}`, exiting")
            await ctx.message.add_reaction("❌")
            await ctx.reply(f"Queue was not moved; room ID `{room_id}` does not match the channel this command was run in. Ensure you run this command in the text channel associated with the judging room `{room_id}`.")
            return

        await ctx.send(self.pprint_judging())

