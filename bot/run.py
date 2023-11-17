'''
Based on Q-Basia's repos:
* https://github.com/Q-Basia/Team_Creation_bot
* https://github.com/Q-Basia/Judging-bot

And JamMack123's repo:
* https://github.com/JamMack123/discord_team_creation_bot
'''

import discord
from discord.ext import commands
from typing import Optional
from discord.utils import get as dget
import os
from dotenv import load_dotenv
import json
import logging
from pathlib import Path
from datetime import datetime
import atexit
import utils

# cogs
from team_cog import Teams
from judging_cog import Judging
from misc_cog import Misc


load_dotenv() # load env vars, like token
args, config = utils.general_setup()

# setup logging
# TODO: move out of utils
file_path = Path(os.path.realpath(__file__)).parents[0] # path to this directory
# log_handler = logging.FileHandler(filename=file_path / 'current.log', encoding='utf-8', mode='w')
# logging.basicConfig(filename=file_path / 'current.log',
#                     filemode='w',
#                     level=logging.DEBUG)

class Bot(commands.Bot):
    def __init__(self, *argv, **kwargv):
        super().__init__(*argv, **kwargv)

# set up permissions
intents = discord.Intents.all() # TODO: use less permisisons
bot = Bot(command_prefix=config['prefix'], intents=intents)

# add cogs
async def setup(bot: commands.Bot):
    await bot.add_cog(Teams(bot))
    await bot.add_cog(Judging(bot))
    await bot.add_cog(Misc(bot))

@bot.event
async def on_ready():
    await setup(bot)
    print(f'Logged in as {bot.user} with config {args.config}')

bot.run(os.environ['TEAMBOT_TOKEN'], log_handler=logging.getLogger().handlers[0])