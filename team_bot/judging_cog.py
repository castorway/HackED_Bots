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

        self.judging_type_msg = None
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
    

    @commands.command(help=f'''Usage: ~set_judging_react_messages <#channel> <type_message_id> <category_message_id>''')
    async def set_judging_react_messages(self, ctx, channel: discord.TextChannel, type_msg_id: str, category_msg_id: str):
        ''' Adds reactions to two messages to act as judging type (online/in-person) and special categories reaction choice menus. '''

        if not check_author_perms(ctx): return
        logging.info(f"set_judging_react_messages called with channel={channel}, type_msg_id={type_msg_id}, category_msg_id={category_msg_id}.")
        
        # verify both messages exist
        try:
            type_msg = await channel.fetch_message(type_msg_id)
            category_msg = await channel.fetch_message(category_msg_id)
        except discord.error.NotFound as e:
            await ctx.message.add_reaction("❌")
            await ctx.reply("Messages were not set; one or both messages could not be found. Check the channel and IDs again.")

        # type (online or in-person)
        await type_msg.add_reaction(config["in-person_react"])
        await type_msg.add_reaction(config["online_react"])
        
        # special categories
        for cat in config["judging_categories"]:
            await category_msg.add_reaction(cat["react"])

        self.judging_type_msg = type_msg
        self.judging_category_msg = category_msg

        logging.info(f"Set judging_type_msg={self.judging_type_msg}")
        logging.info(f"Set judging_category_msg={self.judging_category_msg}")
        await ctx.message.add_reaction("✅")


    @commands.command(help=f'''Usage: `{config['prefix']}make_queues`.''')
    async def make_queues(self, ctx):
        '''
        Automatically generate judging queues for judging rooms defined in config.json, based on the 
        reactions to self.judging_type_msg and self.judging_category_msg.
        
        Requires `set_judging_react_messages` to have been run first.
        '''

        if not check_author_perms(ctx): return
        logging.info(f"make_queues called with channel={channel}, message_id={message_id}.")

        # check we have the messages necessary to make queues
        if self.judging_type_msg == None or self.judging_category_msg == None:
            await ctx.message.add_reaction("❌")
            await ctx.reply("Judging type and category messages haven't been set yet. Ensure you run `set_judging_react_messages` before this command.")

        # get the judging message
        judging_msg = await channel.fetch_message(message_id)

        team_choices = {} # map team name : [each emoji reacted by a member of the team]
        non_team_reacts = []

        # get info from reactions to judging message
        for reaction in judging_msg.reactions:

            # get all the users that added this reaction
            user_list = []
            async for user in reaction.users():
                if user != self.bot.user:
                    user_list.append(user)

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
                    non_team_reacts.append(reaction)

        logging.info(f"make_queues team_choices={team_choices}")
        logging.info(f"make_queues ignored {len(non_team_reacts)} reacts")

        # ===== get highest-priority category for each team

        # make some handy data structures
        icon_to_priority = {} # map emoji : priority
        icon_to_name = {} # map emoji : category name
        category_names = []

        for i, category in enumerate(config['judging_categories']):
            icon_to_priority[category['react']] = i
            icon_to_name[category['react']] = category['name']
            category_names.append(category['name'])

        team_to_category = {} # map team name : category name (to judge them in)
        for team_name, choices in team_choices.items():
            # get name/icon corresponding to highest-priority team chosen
            choose_icon = max(choices, key=lambda e: icon_to_priority[e])
            choose_name = icon_to_name[choose_icon]
            team_to_category[team_name] = choose_name
        
        logging.info(f"make_queues team_to_category={team_to_category}")

        # have done this in several steps so we could possibly implement some kind of preferential
        # sorting in future, not for now though. efficiency isn't a huge concern for this bot

        # ===== now sort teams into judging rooms

        category_to_rooms = {c: [] for c in category_names} # map category name : ids of rooms for this category
        room_ids = config['judging_rooms'].keys()
        for room_id, info in config['judging_rooms'].items():
            category_to_rooms[info['category']].append(room_id)

        judgable_team_names = list(team_to_category.keys())
        random.shuffle(judgable_team_names) # a little shuffle. for fun

        # team_to_room = {} # map team name : room id to send them to
        room_to_teams = {r: [] for r in room_ids} # map room id : teams going to this room
        room_rotate = {c: 0 for c in category_names}

        for team_name in judgable_team_names:
            cat = team_to_category[team_name]
            rooms = category_to_rooms[cat]
            
            if len(rooms) == 1:
                # if only one room for this category, need to use that one
                room_to_teams[rooms[0]].append(team_name)
                # team_to_room[team_name] = rooms[0]

            elif len(rooms) > 1:
                # if multiple rooms for this category, rotate between all available rooms
                r = room_rotate[cat]
                room_to_teams[rooms[r]].append(team_name)
                # team_to_room[team_name] = rooms[r]

                # next time, pick next room in rotation
                room_rotate[cat] = room_rotate[cat] + 1 if room_rotate[cat] + 1 < len(rooms) else 0

            else:
                raise ValueError(f"Category {cat} has no possible rooms.") # this should not happen
                # TODO: modify config checking
            
        logging.info(f"make_queues room_to_teams={room_to_teams}")

        # make a new dict with judging information
        judging = {r: {"next_team": 0, "teams": room_to_teams[r]} for r in room_to_teams.keys()}

        # send info message
        await ctx.reply("This is a json file mapping the *room ID* (as specified in the config.json for this bot) to a list of *team names* (as in the Discord roles). Use it to start judging with the `start_judging` command (be careful with that though).")

        # send generated queue
        await send_as_json(ctx, judging, filename="judging_breakdown.json")


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
            await ctx.reply("Judging was not started; this command must be called with no arguments and exactly one attachment (a json in the same format output by `make_queues`).")

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

        if config["judging_rooms"]["room_id"]["type"] == "online":
            msg = f"Hey {team_role.mention}, you're up next for judging! You are being judged **online**. Please join {config['judging_rooms']['room_id']['channel']} when you are ready."
        elif config["judging_rooms"]["room_id"]["type"] == "in-person":
            msg = f"Hey {team_role.mention}, you're up next for judging! You are being judged **in-person**. Please report to the front desk, where you will be directed to your judging room."

        await channel.send(msg) # send ping

        await ctx.message.add_reaction("✅") # react to original command
