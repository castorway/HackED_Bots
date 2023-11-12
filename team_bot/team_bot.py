'''
Based on Q-Basia's repos:
* https://github.com/Q-Basia/Team_Creation_bot
* https://github.com/Q-Basia/Judging-bot

And JamMack123's repo:
* https://github.com/JamMack123/discord_team_creation_bot
'''

import discord
from discord.ext import commands
from discord.utils import get as dget
import os
from dotenv import load_dotenv
import json
import logging
from pathlib import Path
from datetime import datetime
import atexit
from utils import *

file_path = Path(os.path.realpath(__file__)).parents[0] # get path
load_dotenv() # load env vars, like token

# load config from json
with open(file_path / 'config.json', 'r') as f:
    config = json.load(f)

# additions
config['team_role_colour_obj'] = discord.Colour.from_str(config['team_role_colour'])
config_checks(config)

print(config)

# logging setup
log_handler = logging.FileHandler(filename=file_path / 'team_bot.log', encoding='utf-8', mode='w')
logging.basicConfig(filename=file_path / 'team_bot.log',
                    filemode='w',
                    level=logging.DEBUG)

# bot setup
class Bot(commands.Bot):
    def __init__(self, *argv, **kwargv):
        super().__init__(*argv, **kwargv)

    def team_exists(self, ctx: discord.ext.commands.Context, team_name: str):
        for role in ctx.guild.roles:
            if role.name == team_name:
                if role.color != config['team_role_colour_obj']:
                    logging.warning(f"Team role name {team_name} doesn't have team colour.")
                return True # regardless of colour


intents = discord.Intents.all() # TODO: use less permisisons
bot = Bot(command_prefix=config['prefix'], intents=intents)


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')


@bot.command(help=f'''Usage: {config['prefix']}team SomeTeamName @teammate1 @teammate2 @teammate3
Adds all pinged teammates to the team 'SomeTeamName'.''')
async def team(ctx):

    # ignore if command not issued in team-create channel
    if ctx.message.channel.id != config['team_create_channel_id']:
        print("Ignoring ~team called outside team-create channel")
        return

    team_name = ctx.message.content.split(' ')[1] # get team name
    team_members = list(set([member for member in ctx.message.mentions])) # get unique mentions of users

    logging.info(f"team called with team_name {team_name}, team_members {team_members}")

    for member in team_members:

        # ctx.message.mentions already disincludes role mentions, need to disinclude bots
        if member.bot:
            await ctx.message.add_reaction("❌")
            await ctx.reply(f"Your team was not created; you cannot have a bot on your team!")
            return

        # ensure user not already in team
        for role in member.roles:
            if role.color == config['team_role_colour_obj']:
                await ctx.message.add_reaction("❌")
                await ctx.reply(f"Your team was not created; at least one member is already in a team.")
                return
        
    # ensure team name not already taken
    if bot.team_exists(ctx, team_name):
        await ctx.message.add_reaction("❌")
        await ctx.reply(f"Your team was not created; there is already a team with the name '{team_name}'.")
        return
    
    # ensure number of participants under limit
    if len(team_members) > config['max_team_participants']:
        await ctx.message.add_reaction("❌")
        await ctx.reply(f"Your team was not created; teams can have a maximum of {config['max_team_participants']} participants.")
        return

    # check for empty team
    if len(team_members) == 0:
        await ctx.message.add_reaction("❌")
        await ctx.reply(f"Your team was not created; you cannot have an empty team!")
        return
    
    # ensure all participants aren't already in a team
    for member in team_members:
        for role in member.roles:
            if role.color == config['team_role_colour_obj']:
                logging.info(f"Team {team_name} not created because member {member} already in team.")
                await ctx.message.add_reaction("❌")
                await ctx.reply(f"Your team was not created; at least one member is already in a team.")
                return

    # create team category & role
    team_cat = await ctx.guild.create_category(name=team_name) # category to store team text & vc
    team_role = await ctx.guild.create_role(name=team_name, mentionable=True, colour=config['team_role_colour_obj']) # team role

    # Privatize category so that only team and some others can view
    await team_cat.set_permissions(ctx.message.guild.default_role, read_messages=False) # @everyone can't view
    await team_cat.set_permissions(team_role, read_messages=True)
    for role_name in ['organizer', 'mentor', 'volunteer', 'sponsor']:
        await team_cat.set_permissions(
            dget(ctx.message.guild.roles, id=config['roles'][role_name]), # get role with ID identified in config
            read_messages=True
        )

    # Create the text and voice channel
    team_text = await ctx.guild.create_text_channel(name=team_name, category=team_cat)
    team_vc = await ctx.guild.create_voice_channel(name=team_name, category=team_cat)
    
    # Add created role to all team members
    for member in team_members:
        await member.add_roles(team_role)

    # React in confirmation and send notification in team text channel
    await ctx.message.add_reaction("✅")
    await team_text.send(f'Hey {" ".join([member.mention for member in team_members])}! Here is your team category & channels.')

    logging.info(f"Team created: {team_name}, {[m.name for m in team_members]}, {team_role}")


@bot.command(help=f'''Usage: {config['prefix']}teams_info'. Only usable by Organizer role.''')
async def teams_info(ctx):

    # ignore if user not an organizer
    for role in ctx.author.roles:
        if role.id == config['roles']['organizer']:
            break
    else:
        return

    msg = f"```asciidoc\n"
    msg += f"TEAM INFO\n"
    msg += f"==========================\n"

    for role in ctx.guild.roles:
        if role.colour == config['team_role_colour_obj']:
            msg += f"[{role.name}]\n"
            msg += "".join([f"* {member.name} <{member.id}>\n" for member in role.members])

    msg += "```"

    await ctx.send(msg)
    

bot.run(os.environ['TEAMBOT_TOKEN'], log_handler=log_handler)