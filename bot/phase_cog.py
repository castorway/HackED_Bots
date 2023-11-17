'''
This cog contains commands for switching the 'phase' of the bot (between team creation and judging).
Not currently used.
'''

import discord
from discord.ext import commands
from typing import Optional
from discord.utils import get as dget
import logging
from datetime import datetime
import utils

args, config = utils.general_setup()

class Phase(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def switch_phase(self, phase: str):
        '''
        Switches phase of bot by toggling whether commands are enabled or not. This is put in its own
        command so it can be run at beginning to switch bot to team creation mode. 
        '''
        # in general, these commands should be enabled (or have no reason to be disabled)
        self.bot.get_command("teams_info").update(enabled=True)
        self.bot.get_command("set_judging_react_messages").update(enabled=True)
        self.bot.get_command("auto_make_queues").update(enabled=True)
        self.bot.get_command("vcpull").update(enabled=True)
        
        if phase == "teams":
            # enable creating teams
            self.bot.get_command("create_team").update(enabled=True)
            # disable judging
            self.bot.get_command("start_judging").update(enabled=False)
            self.bot.get_command("next").update(enabled=False)
            return True

        elif phase == "judging":
            # disable creating teams
            self.bot.get_command("create_team").update(enabled=False)
            # enable judging
            self.bot.get_command("start_judging").update(enabled=True)
            self.bot.get_command("next").update(enabled=True)
            return True
        
        else:
            return False

    
    @commands.command(help=f'''Switches the phase of the bot. Restricted.
    Usage: {config['prefix']}phase <phase>

    * phase : may be either "teams" (for team creation phase) or "judging" (for judging phase).''')
    async def phase(self, ctx, phase: str):
        # check permissions
        if not utils.check_perms(ctx.message.author, config["perms"]["can_switch_phase"]):
            logging.info(f"phase: ignoring nonpermitted call by {ctx.message.author.name}")
            return
        
        logging.info(f"phase: called with phase={phase}")
        
        if not self.switch_phase(phase):
            await ctx.message.add_reaction("❌") # react to original command
            await ctx.message.reply("Phase should be one of `teams` or `judging`.")

        await ctx.message.add_reaction("✅") # react to original command
