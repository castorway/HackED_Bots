import discord

def config_checks(config):
    if config['team_role_colour'] == '#000000':
        print("WARNING: Config team role colour should not be #000000! This is used as the default colour for @everyone.")
        exit(0)