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

args, config = utils.general_setup()


class Judging(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.judging = {}

        self.judging_medium_msg = None
        self.judging_category_msg = None


    async def send_as_json(self, ctx, dictionary, filename):
        # make file
        save_filename = utils.gen_filename("autoqueue", "json")
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


    def pprint_judging(self, judging=None, public=False):
        msg = f"# Judging\n"
        # using :scales: instead of emoji bc discord converts emoji to scales character
        if public:
            msg += f"The team indicated by :scales: is the current team being judged (if any). If you are one of the next few teams, we encourage you to report to the front desk (for in-person team members) or your team VC (for online team members) in advance.\n\n"
        else:
            msg += f"The team indicated by :scales: is the current team being judged (if any). The team after it is the team that will be pinged when `~ping <room_id>` is run.\n\n"

        if judging == None:
            judging = self.judging

        for room_id, info in judging.items():
            # room status
            if info["current_team"] < 0:
                status = "Not Started"
            elif info["current_team"] < len(info["teams"]):
                status = "In Progress"
            else:
                status = "Done"
            
            room_display_name = config["judging_rooms"][room_id]['display_name']
            if public:
                msg += f"## {room_display_name} `[{status}]`\n"
            else:
                msg += f"## {room_display_name}\n`[id = {room_id} | {status} | current_team = {info['current_team']}]`\n"

            # print each team
            for i in range(len(info["teams"])):
                team_name = info["teams"][i]
                extra = "" if public else f" {info['extra'][i]}"

                if i < info["current_team"]:
                    msg += f"- `{team_name}`{extra} :white_check_mark:\n"
                elif i == info["current_team"]:
                    msg += f"- `{team_name}`{extra} :scales:\n"
                else:
                    msg += f"- `{team_name}`{extra}\n"
                
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
        '''
        controller = dget(ctx.guild.members, id=config["controller_id"])
        room_channel = dget(ctx.guild.channels, id=config["judging_rooms"][room_id]["text"])
        team_name = self.judging[room_id]["teams"][ self.judging[room_id]["current_team"] ]
        
        await room_channel.send(f"{controller.mention}, a timer has been started assuming `{team_name}` has just started presenting. Ping the next team so they are ready once `{team_name}` is done.")
        
        await asyncio.sleep(60 * 2) # ping them again after 2m

        # if something changed, leave
        if self.judging[room_id]["teams"][ self.judging[room_id]["current_team"] ] != team_name:
            logging.info(f"team_timer: left because team `{team_name}` no longer being judged")
            return
        await room_channel.send(f"{controller.mention}, it's been **2** minutes since `{team_name}` started presenting. Ping the next team again so they are ready once `{team_name}` is done.")

        await asyncio.sleep(60 * 2) # after 4m, ping both them and the team after them

        # if something changed, leave
        if self.judging[room_id]["teams"][ self.judging[room_id]["current_team"] ] != team_name:
            logging.info(f"team_timer: left because team `{team_name}` no longer being judged")
            return
        await room_channel.send(f"{controller.mention}, it's been **4** minutes since `{team_name}` started presenting.\nIf the next team isn't ready, ping both them and the team after.")

        await asyncio.sleep(60 * 1) # after 5m, allotted time is up

        if self.judging[room_id]["teams"][ self.judging[room_id]["current_team"] ] != team_name:
            logging.info(f"team_timer: left because team `{team_name}` no longer being judged")
            return
        await room_channel.send(f"{controller.mention}, it's been **5** minutes since `{team_name}` started presenting, which means their time is up.\nWrap up the presentation, and if there's a team ready to go then send them in.")
    

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

        return team_choices


    @commands.command(help=f'''Automatically generate judging queues, based on the judging rooms defined in this bot's config and the reactions to the messages set using the `set_judging_react_messages` command. Restricted.
    
    Usage: {config['prefix']}auto_make_queues <algorithm> <channel> *[message_ids]
    * algorithm : category_priority
    ''')
    async def auto_make_queues(self, ctx,
        algorithm: str, 
        channel: Optional[discord.TextChannel],
        *react_msg_ids: str
    ):
        '''
        Automatically generate judging queues for judging rooms defined in config.json, based on the 
        reactions to messsages optionally provided.
        '''

        if not utils.check_perms(ctx.message.author, config["perms"]["can_control_judging"]):
            logging.info(f"auto_make_queues: ignoring nonpermitted call by {ctx.message.author.name}")
            return
        
        logging.info(f"auto_make_queues: called with algorithm {algorithm}, channel {channel.name}, react_msg_ids {react_msg_ids}.")

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
            if algorithm == "category_priority":
                # one message id, which should be category reactions
                if len(react_msg_ids) != 1:
                    await ctx.message.add_reaction("❌")
                    await ctx.reply("The `category_priority` mode requires one message ID, which should be the ID participants react to with a category react.")
                    return
                
                category_icons = [info["react"] for cat, info in config["judging_categories"].items()]
                message = await channel.fetch_message(react_msg_ids[0])
                team_category_reacts = await self.get_team_reacts(message, accepted_icons=category_icons)

                logging.info("auto_make_queues: Reactions pulled from the judging messages, by-team:")
                logging.info(pformat(team_category_reacts, indent=4))

                room_to_teams, room_to_extra = queuing.category_priority(team_category_reacts) # some queuing algorithm
                teams_registered = list(team_category_reacts.keys())

            else:
                await ctx.message.add_reaction("❌")
                await ctx.reply("The only modes supported right now are: `category_priority`")
                return

            # make formatted judging dict
            judging = {
                room_id: {
                    "current_team": -1, # signifies that no team is currently in room
                    "teams": room_to_teams[room_id],
                    "extra": room_to_extra[room_id]
                }
                for room_id in room_to_teams.keys()
            }

            # send info message
            await ctx.reply("This is a json file mapping the *room ID* (as specified in the config.json for this bot) to a list of *team names* (as in the Discord roles), as well as a txt log file for the algorithm. Check the txt log file to make sure everything looks right, modify the json as desired, and then use the json to start judging with the `start_judging` command (be careful with that though).")
            
            # send generated queue
            await self.send_as_json(ctx, judging, filename="judging_breakdown.json")
            await ctx.send(file=discord.File(queue_log_name, filename="queue_log.txt"))

            # send info on missed teams:
            teams_not_registered = []
            for role in ctx.guild.roles:
                if role.color == config['team_role_colour_obj']:
                    if role.name not in teams_registered:
                        teams_not_registered.append(role.name)
            
            msg = '\n'.join([f"- `{t}`" for t in teams_not_registered])

            await ctx.send(f"The following teams are in the Discord but did not sign up for judging:\n{msg}")

        except Exception as e:
            # catching arbitrary exception despite bad practice because log handler still needs to be added back
            # if something goes wrong
            logging.error(f"something went wrong in auto_queue! {e}")
            await ctx.message.add_reaction("❌")
            await ctx.reply(f"Something went wrong. Error message:\n```\n{e}```")

        
        # remove special queue logger
        logging.info("auto_make_queues: Finished auto-generating queue.")
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
            await ctx.reply("Judging was not started; this command must be called with no arguments and exactly one attachment (a json in the same format output by `auto_make_queues`).")

        # download the attachment
        # im not a security expert but i can see this being a bit of a hazard. please do not hack my bot
        filename = utils.gen_filename("received", "json")
        
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
                assert -1 <= judging[room_id]["current_team"], f"for room id {room_id}, current_team {judging[room_id]['current_team']} is invalid"

                if len(judging[room_id]["teams"]) > 0:
                    assert judging[room_id]["current_team"] <= len(judging[room_id]["teams"]), f"for room id {room_id}, current_team {judging[room_id]['current_team']} is invalid"
                
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
            if self.judging[room_id]["current_team"] == len(self.judging[room_id]["teams"]) - 1:
                # this is being run while the current team being judged is last in the queue
                logging.info(f"ping: run while final team being judged, not pinging anyone")
                await ctx.message.add_reaction("❌")
                await ctx.reply(f"Team was not pinged; the current team being judged is the final team in the queue.")
                return
            elif self.judging[room_id]["current_team"] > len(self.judging[room_id]["teams"]) - 1:
                # this is being run after all teams have been judged
                logging.info(f"ping: run once queue over, not pinging anyone")
                await ctx.message.add_reaction("❌")
                await ctx.reply(f"Team was not pinged; judging has finished for this room.")
                return
        
            # otherwise, this is being run while a team that is not last in the queue is being judged (or no team is being judged, i.e. current_team == -1)
            # so we want to ping the team that comes after them

            next_team_idx = self.judging[room_id]["current_team"] + 1
            team_name = self.judging[room_id]["teams"][next_team_idx]

            explain_msg = f"Team `{team_name}` is next in line for room `{room_id}` and will be pinged"

        else:
            explain_msg = f"Team `{team_name}` will be pinged"

        # get confirmation
        confirm_msg = await ctx.message.reply(f"{explain_msg}. React to this message with ✅ to confirm, or ❌ to cancel.")
        confirmed = await utils.get_confirmation(self.bot, ctx.message.author, confirm_msg)
        if confirmed == None: # timed out
            return
        elif confirmed == False: # reacted with ❌
            await confirm_msg.reply(f"Team was not pinged.")
            return

        # get the team role and text channel. text channels have weird name restrictions so you need to get the
        # category and then get the channel from that
        ret = self.get_team_artefacts(ctx, team_name)
        if ret == None:
            logging.error(f"couldn't get artefacts for `{team_name}`")
            await ctx.message.add_reaction("❌")
            await ctx.reply(f"There was an issue getting the category or role for this team; you will need to handle them manually.")
            return
        
        team_role, team_cat, team_text, team_vc = ret
        
        # actually ping the team, and send instructions to involved humans
        if config["judging_rooms"][room_id]["medium"] == "online":
            await team_text.send(f"Hey {team_role.mention}, you're up next for judging! You are being judged **online**. Please join {team_vc.mention} as soon as possible, and when the judges are ready you will be moved to the judging room.")
            success_msg = f"Team `{team_name}` was pinged in {team_text.mention} and told to report to {team_vc.mention}.\n"
            success_msg += f"- Keep an eye on {team_vc.mention} to watch for the team joining their VC.\n"
            success_msg += f"- Once they have joined and the current team (if any) is finished presenting, run `~vc_pull` in this channel to move them into the judging VC associated with this room (or manually move them), and inform the controller that the new team has begun presenting."
        
        elif config["judging_rooms"][room_id]["medium"] == "inperson":
            await team_text.send(f"Hey {team_role.mention}, you're up next for judging! You are being judged **in-person**. Please report to the front desk as soon as possible, from where you will be directed to your judging room.")
            success_msg = f"Team `{team_name}` was pinged in {team_text.mention} and told to report to the front desk.\n"
            success_msg += f"- Once they arrive at the front desk, please direct them to **{config['judging_rooms'][room_id]['location']}**, and inform the controller they have been directed to the room.\n"
            success_msg += f"- Once they arrive at {config['judging_rooms'][room_id]['location']}, please inform the controller they have begun presenting."
        
        elif config["judging_rooms"][room_id]["medium"] == "hybrid":
            await team_text.send(f"Hey {team_role.mention}, you're up next for judging!\n- For in-person team members: please report to the front desk as soon as possible, from where you will be directed to your judging room.\n- For online team members: please join {team_vc.mention} as soon as possible, and when the judges are ready you will be moved to the judging room.")
            success_msg = f"Team `{team_name}` was pinged in {team_text.mention} and told to report to the front desk and/or {team_vc.mention}.\n"
            success_msg += f"- Once in-person members arrive at the front desk: direct them to **{config['judging_rooms'][room_id]['location']}**, and inform the controller they have been directed to the room.\n"
            success_msg += f"- Keep an eye on {team_vc.mention} to watch for online members joining their VC. Run `~vcpull {room_id}` or `~vcpull {room_id} {team_name}` to pull them into the judging VC.\n"
            success_msg += f"- Once both in-person and online members are in the room, inform the bot controller they have begun presenting."

        else:
            await ctx.message.add_reaction("❌")
            await ctx.message.reply(f"Config has invalid medium for this judging room. You will have to ping the team manually.")
            return
        
        # send confirmation
        await ctx.message.add_reaction("✅") # react to original command
        await confirm_msg.reply(success_msg)


    @commands.command(help=f'''Moves the judging queue along for the room named `room_id` in the config. To be run once a team has been successfully judged. Restricted.
                      
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
        if self.judging[room_id]["current_team"] == len(self.judging[room_id]["teams"]) - 1:
            # this is being run while the final team is being judged
            logging.info(f"tick: final team is being judged in `{room_id}`, updating log")
            
            self.judging[room_id]["current_team"] += 1 # current_team = len(teams) + 1

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
        
        elif self.judging[room_id]["current_team"] > len(self.judging[room_id]["teams"]) - 1:
            # this is being run after `tick` already run for final team
            logging.info(f"tick: `{room_id}` has no more participants to judge")
            await ctx.message.add_reaction("❌")
            await ctx.reply(f"Queue was not moved; there are no more participants to judge in this room.")
            return
        
        # otherwise, this is being run while a team before the final team is being judged. we need to increment the queue
        # such that 'current team' reflects the team currently being judged in the room, and 'next team' is the team that
        # we want to start pinging with `ping`.

        team_idx = self.judging[room_id]["current_team"]
        
        if team_idx == -1: 
            # judging just started, no team is current_team yet
            team_name = None
            curr_team_name = self.judging[room_id]["teams"][0]
            explain_msg = f"no team has been judged yet, and `{curr_team_name}` is currently being judged"
        else:
            team_name = self.judging[room_id]["teams"][team_idx]
            next_team_name = self.judging[room_id]["teams"][team_idx + 1]
            explain_msg = f"`{team_name}` has finished being judged, and `{next_team_name}` is currently being judged"

        # get confirmation
        confirm_msg = await ctx.message.reply(f"The queue for room `{room_id}` will be moved. This means that {explain_msg}. React to this message with ✅ to confirm, or ❌ to cancel.")
        confirmed = await utils.get_confirmation(self.bot, ctx.message.author, confirm_msg)
        if confirmed == None: # timed out
            return
        elif confirmed == False: # reacted with ❌
            await confirm_msg.reply(f"Queue was not moved.")
            return
        
        # else confirmed == True, move queue along
        self.judging[room_id]["current_team"] += 1

        # log progress and send new json
        judging_log = await self.get_judging_log(ctx)
        msg = f"Moved queue along for room `{room_id}`; {explain_msg}.\n"
        msg += self.pprint_judging(self.judging)

        await judging_log.send(msg)
        await self.send_as_json(judging_log, self.judging, filename="judging_breakdown.json")

        await ctx.message.add_reaction("✅") # react to original command
        await confirm_msg.reply(f"Queue was moved. This means that {explain_msg}.")

        await self.update_public_judging_log(ctx)
        await self.set_team_timer(ctx, room_id)

    
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
        if self.judging[room_id]["current_team"] + 1 == len(self.judging[room_id]["teams"]):
            # no reason to skip the final team! it will just like add them back to the end which makes no sense
            logging.info(f"skip: tried to skip final team in `{room_id}`, exiting")
            await ctx.message.add_reaction("❌")
            await ctx.reply(f"Running `skip` when the queue is at the final team doesn't make sense, they will just be added back to the queue in the same position! Use `next` if you want to clear this team from the queue without judging them.")
            return
        
        elif self.judging[room_id]["current_team"] + 1 > len(self.judging[room_id]["teams"]):
            # this is being run after all teams judged, there is nobody to skip
            logging.info(f"tick: `{room_id}` has no more participants to judge")
            await ctx.message.add_reaction("❌")
            await ctx.reply(f"Queue was not moved; there are no more participants to judge in this room, so there is nobody to skip.")
            return
        
        # otherwise, this is being run while a team before the final team is being judged. we will modify
        # the queue so that 'current team' remains the same team, but 'current team + 1' now refers to the team after
        # this team, and appent this team to the end of the queue for later.

        skip_team_idx = self.judging[room_id]["current_team"] + 1 # index of team to skip (next team)
        skip_team_name = self.judging[room_id]["teams"][skip_team_idx]

        # i know this is inefficient, this bot doesn't need to be running at maximum efficiency tbh
        new_queue = deepcopy(self.judging[room_id]["teams"][:skip_team_idx]) \
                    + deepcopy(self.judging[room_id]["teams"][skip_team_idx+1:]) \
                    + [ self.judging[room_id]["teams"][skip_team_idx] ]

        new_extra = deepcopy(self.judging[room_id]["extra"][:skip_team_idx]) \
                    + deepcopy(self.judging[room_id]["extra"][skip_team_idx+1:]) \
                    + [ self.judging[room_id]["extra"][skip_team_idx] + " (skipped)" ]

        mock_judging = deepcopy(self.judging)
        mock_judging[room_id]["teams"] = new_queue
        mock_judging[room_id]["extra"] = new_extra

        # get confirmation
        msg = f"Team `{skip_team_name}` will be skipped and appended to the end of the queue. The team will be notified that they have been skipped. The new queue will look like this:\n"
        msg += self.pprint_judging(mock_judging)
        msg += "\nReact to this message with ✅ to confirm, or ❌ to cancel."

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
        msg += self.pprint_judging(self.judging)

        await judging_log.send(msg)
        await self.send_as_json(judging_log, self.judging, filename="judging_breakdown.json")

        # notify skipped team they have been skipped

        # get the team role and text channel
        ret = self.get_team_artefacts(ctx, skip_team_name)
        if ret == None:
            logging.error(f"couldn't get artefacts for `{skip_team_name}`")
            await ctx.message.add_reaction("❌")
            await ctx.reply(f"There was an issue getting the category or role for this team; you will need to handle them manually. **They have still been skipped and added to the end of the queue.** Be careful.")
            return
        
        team_role, team_cat, team_text, team_vc = ret
        await team_text.send(f"{team_role.mention} We didn't see you report for judging, so we've skipped your team for now and moved you to the end of our judging queue. If you don't make it when pinged again for your second call time, we will have to exclude your project from the judging.")

        await ctx.message.add_reaction("✅") # react to original command

        await self.update_public_judging_log(ctx)


    @commands.command(help=f'''Moves all participants in the waiting VC to the judging VC, for waiting/judging rooms associated with the text channel this command was run in. Restricted.
    
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
            elif self.judging[room_id]["current_team"] + 1 == len(self.judging[room_id]["teams"]):
                # this was called when the final team is already being judged, there is no next team to pull
                await ctx.message.add_reaction("❌") # react to original command
                await ctx.message.reply("There is no next team to pull into the VC. Make sure you specify the team name if you meant to pull a different team; run `~help vcpull` for more information.")
                return
            else:
                # if a team name was specified, pull from their vc into the judging vc. if not, pull the next-up team (current_team + 1),
                # because next-up team hasn't started presenting yet so they aren't in the vc yet
                next_team_idx = self.judging[room_id]["current_team"] + 1
                team_name = self.judging[room_id]["teams"][next_team_idx]

        ret = self.get_team_artefacts(ctx, team_name)
        if ret == None:
            logging.error(f"couldn't get artefacts for `{team_name}`")
            await ctx.message.add_reaction("❌")
            await ctx.reply(f"There was an issue getting the category or role for this team; you will need to handle them manually.")
            return
        
        team_role, team_cat, team_text, team_vc = ret
        judging_vc = dget(ctx.guild.channels, id=config["judging_rooms"][room_id]["judging_vc"])

        logging.info(team_vc.voice_states)
        print(team_vc.voice_states)
        member_ids = team_vc.voice_states.keys() # people in the team vc

        # get confirmation
        confirm_msg = await ctx.reply(f"There are {len(member_ids)} users in {team_vc.mention} right now who will be moved into {judging_vc.mention}. React to this message with ✅ to confirm, or ❌ to cancel.")
        confirmed = await utils.get_confirmation(self.bot, ctx.message.author, confirm_msg)
        if confirmed == None: # timed out
            return
        elif confirmed == False: # reacted with ❌
            await confirm_msg.reply("Participants were not moved.")
            return

        # move everyone into the judging_vc
        for member_id in member_ids:
            member = dget(ctx.guild.members, id=member_id)
            await member.move_to(judging_vc)

        await ctx.message.add_reaction("✅") # react to original command


    @commands.command(help=f'''Quickly prints the judging queue. Restricted.
    
    Usage: {config['prefix']}q''')
    async def q(self, ctx, public: Optional[str]):
        '''
        This is mostly here as a fast shortcut-ish command to be run when you don't want to switch to the private judging
        log channel. Because you're either incredibly paranoid or just a hardcore gamer.
        '''

        # check permissions
        if not utils.check_perms(ctx.message.author, config["perms"]["can_control_judging"]):
            logging.info(f"q: ignoring nonpermitted call by {ctx.message.author.name}")
            return
        
        if public != None:
            await ctx.send(self.pprint_judging(public=True))
        else:
            await ctx.send(self.pprint_judging())