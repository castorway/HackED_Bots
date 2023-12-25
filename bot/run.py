'''
Based on Q-Basia's repos:
* https://github.com/Q-Basia/Team_Creation_bot
* https://github.com/Q-Basia/Judging-bot

And JamMack123's repo:
* https://github.com/JamMack123/discord_team_creation_bot
'''

import discord
from discord.ext import commands
from discord import app_commands
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
import sys

# cogs
from team_cog import Teams
from judging_cog import Judging
from verification_cog import Verification, add_verification_slash
from misc_cog import Misc


load_dotenv() # load env vars, like token
args, config = utils.general_setup()

# logging setup
utils.logging_setup()
print(logging.getLogger().handlers)

class Bot(commands.Bot):
    def __init__(self, *argv, **kwargv):
        super().__init__(*argv, **kwargv)

# set up permissions
intents = discord.Intents.all() # TODO: use less permisisons
bot = Bot(command_prefix=config['prefix'], intents=intents)

# add slash commands
add_verification_slash(bot)

# add cogs for non-slash commands
async def setup(bot: commands.Bot):
    await bot.add_cog(Teams(bot))
    await bot.add_cog(Judging(bot))
    await bot.add_cog(Verification(bot))
    await bot.add_cog(Misc(bot))

    # await bot.tree.sync(guild=discord.Object(id=config['guild_id'])) # sync slash commands

@bot.event
async def on_ready():
    await setup(bot)
    print(f'Logged in as {bot.user} with config {args.config}')
    

bot.run(os.environ['BOT_TOKEN'])