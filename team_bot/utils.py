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