import discord
from discord.ext import commands
from pathlib import Path
import json
import logging
import os
import asyncio
from datetime import datetime
import argparse
import sys

file_path = Path(os.path.realpath(__file__)).parents[0] # path to this directory

# setup args
parser = argparse.ArgumentParser()
parser.add_argument("-c", "--config", required=True)
parser.add_argument("-o", "--output_dir", default=file_path)
args = parser.parse_args()

output_dir = Path(args.output_dir)


def logging_setup():
    log_name = Path(args.output_dir) / gen_filename("log", "log")

    log_format = logging.Formatter(
        fmt='%(asctime)s %(levelname)-8s [%(filename)s:%(lineno)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    file_handler = logging.FileHandler(filename=log_name, encoding='utf-8', mode='w')
    print_handler = logging.StreamHandler(stream=sys.stdout)

    file_handler.setFormatter(log_format)
    print_handler.setFormatter(log_format)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(print_handler)

    root_logger.propagate = False


def gen_filename(tag, ext):
    """
    Generate a new filename with a timestamp to write data to.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    file_name = output_dir / "generated" / tag / f"{tag}_{timestamp}.{ext}"
    os.makedirs(file_name.parent, exist_ok=True) # doing this here because i will Definitely forget otherwise
    return file_name


def general_setup():
    # load config from json
    with open(args.config, 'r') as f:
        config = json.load(f)

    # additions
    config['team_role_colour_obj'] = discord.Colour.from_str(config['team_role_colour'])
    
    # checks
    if config['team_role_colour'] == '#000000':
        print("WARNING: Config team role colour should not be #000000! This is used as the default colour for @everyone.")
        exit(0)

    return args, config


args, config = general_setup()


async def get_all_team_roles(ctx):
    teams = []
    for role in ctx.guild.roles:
        if role.color == config['team_role_colour_obj']:
            teams.append(role)
    return teams


async def get_confirmation(bot: commands.Bot, confirm_user: discord.User, confirm_msg: discord.Message):
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


def mdprint(team_name):
    """ 
    Removes markdown special characters from a string.
    """
    return team_name.replace('_', '-').replace('*', '-')
