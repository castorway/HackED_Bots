'''
This cog contains commands related to team creation and joining/leaving a team.
'''

import discord
from discord.ext import commands
from typing import Optional
from discord.utils import get as dget
import logging
from datetime import datetime
import utils

args, config = utils.general_setup()

class Teams(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.team_creation_enabled = True

    def team_exists(self, ctx: discord.ext.commands.Context, team_name: str):
        for role in ctx.guild.roles:
            if role.name == team_name and role.color == config['team_role_colour_obj']:
                return True
            

    @commands.command(help=f'''Enables/disables team creation.
    Usage: {config['prefix']}create_team <team_name> *<teammates>
    
    Example: {config['prefix']}create_team MyTeam @teammate1 @teammate2 @teammate3
    Creates the team `MyTeam` and adds the three pinged teammates.''')
    async def turn_team_creation(self, ctx, state: Optional[str]):

        if state == "on":
            self.team_creation_enabled = True
            await ctx.message.add_reaction("✅")
            await ctx.message.reply(f'Team creation enabled.')

        elif state == "off":
            self.team_creation_enabled = False
            await ctx.message.add_reaction("✅")
            await ctx.message.reply(f'Team creation disabled.')

        else:
            await ctx.message.add_reaction("❌")
            await ctx.reply(f"Something was wrong with your command. This command can be run either as `~turn_team_creation on` or `~turn_team_creation off`.")


    @commands.command(help=f'''Creates a new team for the hackathon including all pinged teammates.
    Usage: {config['prefix']}create_team <team_name> *<teammates>
    
    Example: {config['prefix']}create_team MyTeam @teammate1 @teammate2 @teammate3
    Creates the team `MyTeam` and adds the three pinged teammates.''')
    async def create_team(self, ctx):
        ''' 
        Creates a new team with the mentioned users. Performs a bunch of validation to try and avoid pesky
        team name issues later on.
        '''

        # ignore if command not issued in team-create channel
        if ctx.message.channel.id != config['team_create_channel_id']:
            logging.info("Ignoring ~team called outside team-create channel")
            return
        
        # check permissions
        if not utils.check_perms(ctx.message.author, config["perms"]["can_create_team"]):
            logging.info(f"create_team: ignoring nonpermitted call by {ctx.message.author.name}")
            return
        
        # if team creation disabled, exit
        if not self.team_creation_enabled:
            logging.info(f"create_team: ignoring because team creation is disabled")
            await ctx.message.add_reaction("❌")
            await ctx.reply(f"Team creation is disabled.")
            return

        # to get the team name, this splits the message at the first space (to chop off the "~create_team"),
        # and then at the first '<' character (which preceeds a mention)
        x = ctx.message.content.split(maxsplit=1)
        if len(x) < 2:
            await ctx.message.add_reaction("❌")
            await ctx.reply(f"Your team was not created; something is wrong with your command. Run `{config['prefix']}help create_team` for the command usage.")
            return
        team_name = x[1].split('<', maxsplit=1)[0].strip()
        
        # get unique mentions of users for the team members
        team_members = list(set([m for m in ctx.message.mentions]))

        logging.info(f"create_team: called with team_name {team_name}, team_members {[m.name for m in team_members]}")

        for member in team_members:
            # already disincludes role mentions, need to disinclude bots
            if member.bot:
                await ctx.message.add_reaction("❌")
                await ctx.reply(f"Your team was not created; you cannot have a bot on your team.")
                return

            # ensure user not already in team
            for role in member.roles:
                if role.color == config['team_role_colour_obj']:
                    await ctx.message.add_reaction("❌")
                    await ctx.reply(f"Your team was not created; at least one member is already in a team.")
                    return
            
            # ensure user is a participant
            for role in member.roles:
                if role.id == config["roles"]["participant"]:
                    break
            else:
                await ctx.message.add_reaction("❌")
                await ctx.reply(f"Your team was not created; at least one member does not have the `@Participant` role.")
                return
            
        # no backticks because i goddamn said so (it'll break other formatting and make it look ugly)
        if "`" in team_name:

            await ctx.message.add_reaction("❌")
            await ctx.reply(f"Your team was not created; please don't use backtick (`) characters in your team name.")
            return

        # ensure team name not already taken
        if self.team_exists(ctx, team_name):
            await ctx.message.add_reaction("❌")
            await ctx.reply(f"Your team was not created; there is already a team with the name `{team_name}`.")
            return
        
        # ensure team name won't cause conflicts with anything already in the server
        if dget(ctx.message.guild.channels, name=team_name) \
            or dget(ctx.message.guild.categories, name=team_name) \
            or dget(ctx.message.guild.channels, name=team_name) \
            or dget(ctx.message.guild.roles, name=team_name):

            await ctx.message.add_reaction("❌")
            await ctx.reply(f"Your team was not created; the name `{team_name}` is not allowed.")
            return
        
        # ensure number of participants under limit
        if len(team_members) > config['max_team_participants']:
            await ctx.message.add_reaction("❌")
            await ctx.reply(f"Your team was not created; teams can have a maximum of {config['max_team_participants']} participants.")
            return

        # check for empty team
        if len(team_members) == 0:
            await ctx.message.add_reaction("❌")
            await ctx.reply(f"Your team was not created; you cannot have an empty team.")
            return
                
        # ensure team name only uses ASCII characters (some fancy characters will break things later on, and i dont like taking risks)
        if not all(ord(c) < 128 for c in team_name):
            await ctx.message.add_reaction("❌")
            await ctx.reply(f"Your team was not created; the name `{team_name}` uses invalid characters.")
            return
        
        # get confirmation from sender
        confirm_msg = await ctx.reply(f"The team `{team_name}` will be created, and members {' '.join([m.mention for m in team_members])} will be added.\n\n{ctx.message.author.mention}, please react to this message with ✅ to confirm, or ❌ to cancel.")
        confirmed = await utils.get_confirmation(self.bot, ctx.message.author, confirm_msg)

        if confirmed == None:
            # timed out
            return
        elif confirmed == False:
            # reacted with ❌
            await confirm_msg.reply(f"Team {team_name} was not created.")
            return
        # otherwise, user confirmed, so we can proceed

        # create team category & role
        team_cat = await ctx.guild.create_category(name=team_name) # category to store team text & vc
        team_role = await ctx.guild.create_role(name=team_name, mentionable=True, colour=config['team_role_colour_obj']) # team role

        # Privatize category so that only team and some others can view
        await team_cat.set_permissions(ctx.message.guild.default_role, read_messages=False) # @everyone can't view
        await team_cat.set_permissions(team_role, read_messages=True)
        for role_name in ['organizer', 'mentor', 'volunteer', 'sponsor']:
            await team_cat.set_permissions(
                dget(ctx.message.guild.roles, id=config['roles'][role_name]), # get role with ID identified in config
                read_messages=True
            )

        # Create the text and voice channel
        team_text = await ctx.guild.create_text_channel(name=team_name, category=team_cat)
        team_vc = await ctx.guild.create_voice_channel(name=team_name, category=team_cat)
        
        # Add created role to all team members
        for member in team_members:
            await member.add_roles(team_role)

        # React in confirmation and send notification in team text channel
        await ctx.message.add_reaction("✅")
        await team_text.send(f'Hey {" ".join([member.mention for member in team_members])}! Here is your team category & channels.')

        logging.info(f"Team created: {team_name}, {[m.name for m in team_members]}, {team_role}")


    @commands.command(help=f'''Sends information about all teams currently created on the server. Restricted.
    Usage: {config['prefix']}teams_info''')
    async def teams_info(self, ctx):

        # check permissions
        if not utils.check_perms(ctx.message.author, config["perms"]["can_teams_info"]):
            logging.info(f"next: ignoring nonpermitted call by {ctx.message.author.name}")
            return
        
        logging.info(f"teams_info: called")

        msg = f"```asciidoc\n"
        msg += f"TEAMS\n"
        msg += f"==========================\n"

        for role in ctx.guild.roles:
            if role.colour == config['team_role_colour_obj']:
                msg += f"[{role.name}]\n"
                msg += "".join([f"* {member.name} <{member.id}>\n" for member in role.members])

        msg += "```"

        await ctx.send(msg)
    