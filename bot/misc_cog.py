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


class Misc(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.command(help=f'''Validates the bot's config for this server. Restricted.
    
    Usage: {config['prefix']}validate_config''')
    async def validate_config(self, ctx):

        if not utils.check_perms(ctx.message.author, config["perms"]["can_control_judging"]):
            logging.info(f"auto_make_queues: ignoring nonpermitted call by {ctx.message.author.name}")
            return
        
        logging.info(f"validate_config: called.")

        try:
            controller = dget(ctx.guild.members, id=config["controller_id"])
            assert controller != None, "controller_id does not belong to server member"
            await ctx.send(f"- `controller_id` belongs to {controller.mention}")

            for role, role_id in config["roles"].items():
                r = dget(ctx.guild.roles, id=role_id)
                assert r != None, f"role id for {role} broken"
                await ctx.send(f"- role id for `{role}` is {r.mention}")

            for channel in ["private_judging_log_channel_id", "public_judging_log_channel_id"]:
                c = dget(ctx.guild.channels, id=config[channel])
                assert r != None, f"channel id for {channel} broken"
                await ctx.send(f"- channel for `{channel}` is {c.mention}")

            for cat, info in config["judging_categories"].items():
                for room in info["rooms"]:
                    assert room in config["judging_rooms"].keys(), f"info for room {room} not specified"
                await ctx.send(f"- room IDs specified for category `{cat} (react={info['react']}, priority={info['priority']})` are `{info['rooms']}`, all are specified in `judging_rooms`")

            for room, info in config["judging_rooms"].items():
                assert "display_name" in info.keys(), f"no display_name for room {room}"
                assert "medium" in info.keys(), f"no medium for room {room}"
                assert "location" in info.keys(), f"no location for room {room}"
                assert "text" in info.keys(), f"no text channel id for room {room}"
                assert "judging_vc" in info.keys(), f"no judging_vc for room {room}"
                await ctx.send(f"- all keys specified for room `{room}`")

                assert info["medium"] in ["online", "inperson", "hybrid"], f"invalid medium {room['medium']} for room {room}"

                c = dget(ctx.guild.channels, id=info["text"])
                assert r != None, f"text channel id for {room} broken"
                await ctx.send(f"- text channel for `{room}` is {c.mention}")

                c = dget(ctx.guild.channels, id=info["judging_vc"])
                assert r != None, f"voice channel id for {room} broken"
                await ctx.send(f"- voice channel for `{room}` is {c.mention}")

        except Exception as e:
            logging.error(e)
            print(e)
            await ctx.send(f"**Something's wrong with the config! This is probably an urgent problem.** Unless it's just an issue with the `validate_config` command, which is totally possible.\n```\n{e}\n```")

        await ctx.message.reply(f"Config looks okay. Verify all the channels and roles are correct.")