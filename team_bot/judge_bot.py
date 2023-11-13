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


@bot.command(help=f'''Usage: `{config['prefix']}setup_judging`.''')
async def setup_judging(ctx):

    print(ctx.content)
    print(ctx.mentions)
    print(ctx.channels)
    
    # get all teams
    team_roles = []
    for role in ctx.guild.roles:
        if role.color == config['team_role_colour_obj']:
            team_roles.append(role)

    # get reactions to judging message
    judging_msg = discord.utils.get(bot.cached_messages, id=msg.id) #or client.messages depending on your variable
    print(cache_msg.reactions)


bot.run(os.environ['TEAMBOT_TOKEN'], log_handler=log_handler)