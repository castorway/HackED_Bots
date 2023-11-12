import discord

class Team():
    def __init__(self):
        members = []
        category = None
        text_channel = None
        voice_channel = None

    def add(self, member: discord.User):
        self.members.append(member)


class JudgingRoom():
    def __init__(self):
        room_no = None
        judges = []


def config_checks(config):
    if config['team_role_colour'] == '#000000':
        print("WARNING: Config team role colour should not be #000000! This is used as the default colour for @everyone.")
        exit(0)