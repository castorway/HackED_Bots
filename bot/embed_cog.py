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


    @commands.command(help=f'''Send a template embed. Restricted.
    
    Usage: {config['prefix']}te "some header" "some content..."''')
    async def embed_t(self, ctx, title: str, content: str):
        '''
        Make embeds in the special format that I use for the HackED server.
        Exists so we don't need YAGPDB, and to make writing all these embed
        messages slightly less time-consuming.
        '''
        if not utils.check_perms(ctx.message.author, config["perms"]["controller"]):
            logging.info(f"embed_t: ignoring nonpermitted call by {ctx.message.author.name}")
            return

        embed = discord.Embed(
            title=title,
            description=content,
            color=0x00F3E9,
        )
        await ctx.send(embed=embed)
        await ctx.message.add_reaction("✅")


    @commands.command(help=f'''Edits a message with a template embed. Restricted.
    
    Usage: {config['prefix']}embedit_t "some header" "some content..."''')
    async def embedit_t(self, ctx, channel: discord.TextChannel, message_id: str, title: str, content: str):
        if not utils.check_perms(ctx.message.author, config["perms"]["controller"]):
            logging.info(f"embedit_t: ignoring nonpermitted call by {ctx.message.author.name}")
            return
        
        embed = discord.Embed(
            title=title,
            description=content,
            color=0x00F3E9,
        )

        # edit the message
        embed_message = await channel.fetch_message(message_id)
        await embed_message.edit(embed=embed)
        await ctx.message.add_reaction("✅")

        
    @commands.command(help=f'''Send a custom embed. Restricted.
    
    Usage: {config['prefix']}embed_c "some header" "some content..."''')
    async def embed_c(self, ctx, contents: str):
        if not utils.check_perms(ctx.message.author, config["perms"]["controller"]):
            logging.info(f"embed_c: ignoring nonpermitted call by {ctx.message.author.name}")
            return
        
        contents = ctx.message.content.strip(f"{config['prefix']}embed_c ")
        embed = discord.Embed.from_dict(json.loads(contents))

        await ctx.send(embed=embed)
        await ctx.message.add_reaction("✅")


    @commands.command(help=f'''Edits a message with a custom embed. Restricted.
    
    Usage: {config['prefix']}embedit_c "some header" "some content..."''')
    async def embedit_c(self, ctx, channel: discord.TextChannel, message_id: str):
        if not utils.check_perms(ctx.message.author, config["perms"]["controller"]):
            logging.info(f"embedit_c: ignoring nonpermitted call by {ctx.message.author.name}")
            return

        # embed contents are rest of command after message_id
        contents = ctx.message.content.split(None, 3)[3] 
        print(message_id)
        print(contents)

        embed = discord.Embed.from_dict(json.loads(contents.strip()))

        # edit the message
        embed_message = await channel.fetch_message(message_id)
        await embed_message.edit(embed=embed)
        await ctx.message.add_reaction("✅")


