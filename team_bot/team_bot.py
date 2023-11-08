'''
Based on Q-Basia's repos:
* https://github.com/Q-Basia/Team_Creation_bot
* https://github.com/Q-Basia/Judging-bot

And JamMack123's repo:
* https://github.com/JamMack123/discord_team_creation_bot
'''

import discord
from discord.ext import commands
from discord.utils import get as dget
import os
from dotenv import load_dotenv
import json
import logging
from pathlib import Path
from datetime import datetime
import atexit

# get path
file_path = Path(os.path.realpath(__file__)).parents[0]

# load env vars like token
load_dotenv()

# load config from json
with open(file_path / 'config.json', 'r') as f:
    config = json.load(f)
print(config)

# logging setup
log_handler = logging.FileHandler(filename=file_path / 'team_bot.log', encoding='utf-8', mode='w')
logging.basicConfig(filename=file_path / 'team_bot_script.log',
                    filemode='w',
                    level=logging.DEBUG)

# bot setup
class Bot(commands.Bot):
    def __init__(self, *argv, **kwargv):
        super().__init__(*argv, **kwargv)

        # load teams; teams dict should map team_name to dict of team info
        self.teams_path = file_path / "teams.json"

        try:
            # load the teams.json file
            with open(self.teams_path, "r") as f:
                self.teams = json.loads(f)
        except (FileNotFoundError, TypeError) as e:
            # warn and create a new empty teams dict
            logging.warning(e)
            logging.info("Creating an empty teams dict.")
            self.teams = {}

        logging.info(f"Loaded teams: {list(self.teams.keys())}")

    def add_team(self, team_id: int, team_dict: dict):
        ''' Add a team to teams dict. '''
        if team_id in self.teams.keys():
            logging.warning(f"Tried to add an already-existing team id={team_id} with info={team_dict}.")
            raise KeyError(f"Tried to add an already-existing team id={team_id} with info={team_dict}.")
        else:
            self.teams[team_id] = team_dict
            print(f"ADD TEAM CALLED {team}")

    def team_exists(self, team_name: str):
        return team_name in self.teams.keys()

    def recreate_json(self):
        ''' Recreate teams json and make a backup of the old one. '''
        try:
            # if there is an old teams.json, keep as backup
            if os.path.exists(self.teams_path):
                bk_path = file_path / 'backup' / f'teams_{datetime.now().strftime("%m-%d_%H-%M-%S")}.json'
                os.makedirs(bk_path.parent, exist_ok=True)
                os.rename(self.teams_path, bk_path)
            
            # dump data to new teams.json
            with open(self.teams_path, "w") as f:
                self.teams = json.dump(self.teams, f)
            
            logging.info(f"Recreated teams.json.")

        except Exception as e:
            logging.warning(f"Recreating teams.json failed with error: {e}")

    def cleanup(self):
        ''' Save any data. Should be run at end when program exits. '''
        self.recreate_json() # save teams json



intents = discord.Intents.all() # TODO: fix this
bot = Bot(command_prefix=config['prefix'], intents=intents)

@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')

@bot.command(help=f'''Usage: {config['prefix']}team SomeTeamName @teammate1 @teammate2 @teammate3
Adds all pinged teammates to the team 'SomeTeamName'.''')
async def team(ctx):

    # ignore if command not issued in team-create channel
    if ctx.message.channel.id != config['team_create_channel_id']:
        print("Ignoring ~team called outside team-create channel")
        return
    
    # ensure number of participants under limit
    team_members = list(set([member for member in ctx.message.mentions]))
    if len(team_members) > config['max_team_participants']:
        await ctx.message.add_reaction("❌")
        await ctx.reply(f"Your team was not created; teams can have a maximum of {config['max_team_participants']} participants.")
        return
    
    # ensure all participants aren't already in a team
    for member in team_members:
        for role in member.roles:
            if role.id in bot.teams:
                await ctx.message.add_reaction("❌")
                await ctx.reply(f"Your team was not created; teams can have a maximum of {config['max_team_participants']} participants.")
                return

    team_name = ctx.message.content.split(' ')[1] # get team name

    # ensure team name not already taken
    if bot.team_exists(team_name):
        await ctx.message.add_reaction("❌")
        await ctx.reply(f"Your team was not created; there is already a team with the name '{team_name}'.")
    
    team_cat = await ctx.guild.create_category(name=team_name) # category to store team text & vc
    team_role = await ctx.guild.create_role(name=team_name, mentionable=True) # team role

    # Privatize category so that only team and some others can view
    await team_cat.set_permissions(ctx.message.guild.default_role, read_messages=False) # @everyone can't view
    await team_cat.set_permissions(team_role, read_messages=True)
    for role_name in ['organizer', 'mentor', 'volunteer', 'sponsor']:
        await team_cat.set_permissions(
            dget(ctx.message.guild.roles, id=config['roles'][role_name]),
            read_messages=True
        )

    # Create the text and voice channel
    team_text = await ctx.guild.create_text_channel(name=team_name, category=team_cat)
    team_vc = await ctx.guild.create_voice_channel(name=team_name, category=team_cat)
    
    # Add created role to all team members
    for member in team_members:
        await member.add_roles(team_role)

    # Store info in Bot object
    team_info = {
        "member_ids": [member.id for member in team_members],
        "role_id": team_role.id,
        "category_id": team_cat.id,
        "text_id": team_text.id,
        "vc_id": team_vc.id,
    }
    bot.add_team(team_name, team_info)

    # React in confirmation and send notification in team text channel
    await ctx.message.add_reaction("✅")
    await team_text.send(f'Hey {" ".join([member.mention for member in team_members])}! Here is your team category & channels.')


# register cleanup functions
def cleanup():
    logging.info("atexit cleanup handler")
    bot.cleanup()
atexit.register(cleanup)

bot.run(os.environ['TEAMBOT_TOKEN'], log_handler=log_handler)