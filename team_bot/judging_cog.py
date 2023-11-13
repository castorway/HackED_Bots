import discord
from discord.ext import commands
from typing import Optional
from discord.utils import get as dget
import logging
from datetime import datetime
from utils import general_setup

config = general_setup()


class Judging(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(help=f'''Usage: `{config['prefix']}setup_judging`.''')
    async def setup_queues(self, ctx, channel: Optional[discord.TextChannel], message_id: Optional[str]):

        # print(ctx.message.content)
        # print(ctx.message.mentions)

        print(channel, type(channel))
        print(message_id, type(message_id))

        logging.info(f"setup_queues called with channel={channel}, message_id={message_id}.")

        # hastily check arguments
        if channel == None or not message_id.isdigit(): 
            await ctx.reply(f"Something's wrong with your arguments.")
            return

        # get the judging message
        judging_msg = await channel.fetch_message(message_id)

        team_choices = {}
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

        logging.info(f"setup_teams team_choices={team_choices}")
        logging.info(f"setup_teams ignored {len(non_team_reacts)} reacts")

        # make config into better data structure for this
        priorities_map = {}
        for i, cat in enumerate(config['judging_categories']):
            priorities_map[cat['react']] = i

        # pick highest-priority category for this team
        team_decision = {}
        for team_name, choices in team_choices.items():
            # get icon corresponding to highest-priority team chosen
            team_decision[team_name] = max(choices, key=lambda e: priorities_map[e])
        
        logging.info(f"setup_teams team_decision={team_decision}")

        # have done this in two steps so we could possibly implement some kind of preferential
        # sorting in future, not for now though. efficiency isn't a huge concern for this bot
        