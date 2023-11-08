'''
super quick script to kick all users except for ones with a particular role 
from a server, used to clear out the old HackED servers.

requires bot role to be moved above all roles to be kicked. did this because
im kinda paranoid and wanted to give the thing as few permissions as possible

requires only 'Kick Members' permission
'''

import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

# load env vars like token
load_dotenv()

# bot setup
intents = discord.Intents.default()
intents.message_content = True # need for seeing command content
intents.members = True # need for seeing all members
bot = commands.Bot(command_prefix='~', intents=intents)


@bot.command()
async def kick_except(ctx, role: discord.Role, dryrun="dry"):
    kicked, spared_role, spared_bot, forbode = 0, 0, 0, 0

    for member in ctx.guild.members:
        if role in member.roles:
            spared_role += 1
            print(f'spared (role) {member}')
            continue
        if member.bot:
            spared_bot += 1
            print(f'spared (bot) {member}')
            continue

        try:
            if dryrun == "nondry":
                await member.kick()
            else:
                print(f'kick {member}')
            kicked += 1

        except discord.errors.Forbidden:
            print(f'failed to kick {member}, Forbidden')
            forbode += 1

    await ctx.channel.send(f'kicked: {kicked}\nspared (role): {spared_role}\nspared (bot): {spared_bot}\nforbode: {forbode}')
                    

bot.run(os.environ['TOKEN'])