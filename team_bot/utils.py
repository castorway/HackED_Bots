import discord
from pathlib import Path
import json
import logging
import os

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