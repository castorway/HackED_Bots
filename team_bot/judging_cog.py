import discord
from discord.ext import commands
from typing import Optional
from discord.utils import get as dget
import logging
from datetime import datetime
from utils import general_setup
import random
import os
import json

config = general_setup()

async def send_as_json(ctx, dictionary, filename):
    temp_name = Path("./_temp.json")

    # make file
    os.makedirs('')
    with open(temp_name, "w") as f:
        f.write(json.dumps(dictionary, indent=4))

    # send file
    await ctx.send(file=discord.File(temp_name), filename=filename)

    # get rid of file
    os.remove(temp_name)


class Judging(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}

    
    @commands.command(help=f'''Usage: `{config['prefix']}make_judging_queues`.''')
    async def make_judging_queues(self, ctx, channel: Optional[discord.TextChannel], message_id: Optional[str]):

        print("what", channel, type(channel))
        print(message_id, type(message_id))

        print(0)

        logging.info(f"make_judging_queues called with channel={channel}, message_id={message_id}.")

        print(1)

        # hastily check arguments
        if channel == None or not message_id.isdigit(): 
            await ctx.reply(f"Something's wrong with your arguments.")
            return

        # get the judging message
        judging_msg = await channel.fetch_message(message_id)

        print(2)

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

        logging.info(f"make_judging_queues team_choices={team_choices}")
        logging.info(f"make_judging_queues ignored {len(non_team_reacts)} reacts")

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
        
        logging.info(f"make_judging_queues team_to_category={team_to_category}")

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
            
        logging.info(f"make_judging_queues room_to_teams={room_to_teams}")

        print("?????")

        # send generated queue
        send_as_json(ctx, room_to_teams, filename="judging_breakdown.json")


    @commands.command(help=f'''Usage: `{config['prefix']}make_judging_queues`.''')
    async def make_judging_queues(self, ctx, channel: Optional[discord.TextChannel], message_id: Optional[str]):

        print(channel, type(channel))
        print(message_id, type(message_id))