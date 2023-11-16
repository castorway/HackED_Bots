import discord
from pathlib import Path
import json
import logging
import os
import asyncio

file_path = Path(os.path.realpath(__file__)).parents[0] # path to this directory

def general_setup():
    # load config from json
    with open(file_path / 'config.json', 'r') as f:
        config = json.load(f)

    # additions
    config['team_role_colour_obj'] = discord.Colour.from_str(config['team_role_colour'])
    
    # checks
    if config['team_role_colour'] == '#000000':
        print("WARNING: Config team role colour should not be #000000! This is used as the default colour for @everyone.")
        exit(0)

    # logging setup
    log_handler = logging.FileHandler(filename=file_path / 'team_bot.log', encoding='utf-8', mode='w')
    logging.basicConfig(filename=file_path / 'team_bot.log',
                        filemode='w',
                        level=logging.DEBUG)

    return config


config = general_setup()


async def get_all_team_roles(ctx):
    teams = []
    for role in ctx.guild.roles:
        if role.color == config['team_role_colour_obj']:
            teams.append(role)
    return teams


async def get_confirmation(bot: discord.ext.commands.Bot, confirm_user: discord.User, confirm_msg: discord.Message):
    '''
    Waits for `confirm_user` to react to `confirm_message`.
    If the user reacts with ✅, it returns True.
    If the user reacts with ❌, it returns False.
    If the program times out (after 20s), it returns None.
    '''

    await confirm_msg.add_reaction("✅")
    await confirm_msg.add_reaction("❌")
    # TODO: consider char limit

    def check(reaction, user):
        return user == confirm_user and reaction.emoji in ["✅", "❌"]

    # waiting for reaction confirmation
    try:
        reaction, user = await bot.wait_for('reaction_add', check=check, timeout=20.0) # 20 second timeout
    except asyncio.TimeoutError:
        await confirm_msg.reply("Timed out waiting for confirmation; please rerun the command if you want to try again.")
        return None

    if reaction.emoji == "✅":
        return True
    else:
        return False
    

def check_perms(user, allowed_roles):
    """ 
    Checks that user has one of the roles in `allowed_roles` (which is a list containing string names
    of roles, as they appear in the config).
    """
    allowed_ids = [config["roles"][r] for r in allowed_roles]
    for role in user.roles:
        if role.id in allowed_ids:
            return True
    else:
        return False