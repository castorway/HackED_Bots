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


class Embed(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.command(help=f'''Send an embed. Restricted.
    
    Usage: {config['prefix']}te "some header" "some content..."''')
    async def embed_t(self, ctx, header: str, content: str):
        '''
        Make embeds in the special format that I use for the HackED server.
        Exists so we don't need YAGPDB, and to make writing all these embed
        messages slightly less time-consuming.
        '''

        embed = discord.Embed(
            title="",
            url="",
            description=f"## {header}\n{content}",
            color=0x00F3E9,
        )
        
        await ctx.send(embed)
        await ctx.message.add_reaction("✅")
        
    
    @commands.command(help=f'''Send a custom embed. Restricted.
    
    Usage: {config['prefix']}ce "some header" "some content..."''')
    async def embed_c(self, ctx, contents: str):
        '''
        Send custom embed from JSON text.
        '''

        contents = ctx.message.content.strip(f"{config['prefix']}ce ")

        embed = discord.Embed.from_dict(json.loads(contents))

        await ctx.send(embed=embed)
        await ctx.message.add_reaction("✅")