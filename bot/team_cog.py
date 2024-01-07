'''
This cog contains commands related to team creation and joining/leaving a team.
'''

import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional, List
from discord.utils import get as dget
import logging
from datetime import datetime
import utils
import re
import database

args, config = utils.general_setup()

class Teams(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.team_creation_enabled = True
            

    @commands.command(help=f'''Enables/disables team creation. Restricted.
    Usage: {config['prefix']}turn_team_creation [on|off]''')
    async def turn_team_creation(self, ctx, state: Optional[str]):

        # check permissions
        if not utils.check_perms(ctx.message.author, config["perms"]["controller"]):
            logging.info(f"turn_team_creation: ignoring nonpermitted call by {ctx.message.author.name}")
            return

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


    @commands.command(help=f'''Sends information about all teams currently created on the server. Restricted. Cannot be run in a public channel.
    Usage: {config['prefix']}all_teams_info''')
    async def all_teams_info(self, ctx):

        # check permissions
        if not utils.check_perms(ctx.message.author, config["perms"]["can_teams_info"]):
            logging.info(f"all_teams_info: ignoring nonpermitted call by {ctx.message.author.name}")
            return
        
        # check channel is bot channel
        if ctx.message.channel.id != config["channels"]["bot"]:
            logging.info(f"all_teams_info: ignoring call in wrong channel by {ctx.message.author.name}")
            await ctx.message.reply("This command cannot be run here.")
            return
        
        logging.info(f"all_teams_info: called")

        # get info and send
        all_info = database.get_teams_info(ctx.message.guild)

        msg = f"# TEAMS\n"
        char_count = len(msg) # for ``` at end

        for team_name, info in all_info.items():
            # write team name and members of team
            add_to_msg = f"## **`{team_name}`:**\n"

            channel_mentions = [f"{info[ref].mention}" for ref in ["team_text", "team_vc", "team_role"]]
            add_to_msg += "- `DISCORD:` " + " | ".join(channel_mentions) + "\n"

            member_mentions = [f"{m['member_object'].mention}" for m in info["team_members"] if m['member_object'] != None]
            add_to_msg += "- `MEMBERS:` " + ", ".join(member_mentions) + "\n"

            char_count += len(add_to_msg) # char count including this team

            if char_count < 1990: # 10 char padding just in case i messed this up
                msg += add_to_msg

            else:
                # send this msg
                await ctx.send(msg)

                # new msg
                msg = add_to_msg
                char_count = len(msg)

        await ctx.send(msg)


    @commands.command(help=f'''Sends information about a team currently created on the server. Restricted. Cannot be run in a public channel.
    Usage: {config['prefix']}team_info''')
    async def team_info(self, ctx, team_name: str):

        # check permissions
        if not utils.check_perms(ctx.message.author, config["perms"]["can_teams_info"]):
            logging.info(f"team_info: ignoring nonpermitted call by {ctx.message.author.name}")
            return
        
        # check channel is bot channel
        if ctx.message.channel.id != config["channels"]["bot"]:
            logging.info(f"team_info: ignoring call in wrong channel by {ctx.message.author.name}")
            await ctx.message.reply("This command cannot be run here.")
            return

        msg = database.get_team_display(ctx, team_name)
        await ctx.reply(msg)


    @commands.command(help=f'''Add a participant to a team, modifying its list of members. Restricted.
    Usage: {config['prefix']}add_to_team <team_name> <member>
    Example: {config['prefix']}add_to_team some-team @sintacks''')
    async def add_to_team(self, ctx):
        # check permissions
        if not utils.check_perms(ctx.message.author, config["perms"]["controller"]):
            logging.info(f"add_to_team: ignoring nonpermitted call by {ctx.message.author.name}")
            return
        
        logging.info(f"add_to_team called with contents: {ctx.message.content}")

        # get arguments (team name and mentioned member)
        _, team_name, __ = ctx.message.content.split(maxsplit=2)
        members = ctx.message.mentions
        logging.info(f"team_name={team_name}, members={members}")
        
        # enforce only 1 member
        if len(members) != 1:
            await ctx.message.add_reaction("❌")
            await ctx.message.reply(f"Team was not modified; ensure you are running the command in the correct format.")
            return
        member = members[0]

        # get confirmation
        confirm_msg = await ctx.message.reply(f"{member.mention} will be **added to** team `{team_name}`. React to this message with ✅ to confirm, or ❌ to cancel.")
        confirmed = await utils.get_confirmation(self.bot, ctx.message.author, confirm_msg)
        if confirmed == None: # timed out
            return
        elif confirmed == False: # reacted with ❌
            await confirm_msg.reply(f"Team was not modified.")
            return

        # perform operation
        success, msg = database.add_to_team(team_name, member)

        if success:
            # also give team role to participant
            await member.add_roles(database.get_team_role(ctx.message.guild, team_name))
            emote = "✅"
        else:
            emote = "❌"
        
        await confirm_msg.reply(emote + ' ' + msg)


    @commands.command(help=f'''Remove a participant from a team, modifying its list of members. Restricted.
    Usage: {config['prefix']}remove_from_team <team_name> <member>
    Example: {config['prefix']}remove_from_team some-team @sintacks''')
    async def remove_from_team(self, ctx):
        # check permissions
        if not utils.check_perms(ctx.message.author, config["perms"]["controller"]):
            logging.info(f"remove_from_team: ignoring nonpermitted call by {ctx.message.author.name}")
            return
        
        logging.info(f"remove_from_team called with contents: {ctx.message.content}")

        # get arguments (team name and mentioned member)
        _, team_name, __ = ctx.message.content.split(maxsplit=2)
        members = ctx.message.mentions
        logging.info(f"team_name={team_name}, members={members}")
        
        # enforce only 1 member
        if len(members) != 1:
            await ctx.message.add_reaction("❌")
            await ctx.message.reply(f"Team was not modified; ensure you are running the command in the correct format.")
            return
        member = members[0]

        # get confirmation
        confirm_msg = await ctx.message.reply(f"{member.mention} will be **removed from** team `{team_name}`. React to this message with ✅ to confirm, or ❌ to cancel.")
        confirmed = await utils.get_confirmation(self.bot, ctx.message.author, confirm_msg)
        if confirmed == None: # timed out
            return
        elif confirmed == False: # reacted with ❌
            await confirm_msg.reply(f"Team was not modified.")
            return
        
        # perform operation
        success, msg = database.remove_from_team(team_name, member)
        
        if success:
            # also remove team role from participant
            await member.remove_roles(database.get_team_role(ctx.message.guild, team_name))
            emote = "✅"
        else:
            emote = "❌"

        await confirm_msg.reply(emote + ' ' + msg)
    

"""
    @commands.command(help=f'''Edits a team, modifying its name. Restricted.
    Usage: {config['prefix']}change_team_name <old_name> <new_name>
    ''')
    async def change_team_name(self, ctx):

        # check permissions
        if not utils.check_perms(ctx.message.author, config["perms"]["controller"]):
            logging.info(f"turn_team_creation: ignoring nonpermitted call by {ctx.message.author.name}")
            return

        args = ctx.message.content.split()
        old_name, new_name = args[1], args[2]

        # get confirmation
        confirm_msg = await ctx.message.reply(f"Team `{old_name}` will be **renamed to** `{new_name}`. React to this message with ✅ to confirm, or ❌ to cancel.")
        confirmed = await utils.get_confirmation(self.bot, ctx.message.author, confirm_msg)
        if confirmed == None: # timed out
            return
        elif confirmed == False: # reacted with ❌
            await confirm_msg.reply(f"Team was not modified.")
            return

        success, message = database.change_team_name(old_name, new_name)
        if success:
            # get team artefacts
            team_info = database.get_team_info(ctx.guild, new_name)

            # also change role and channel names
            await self.bot.edit_role(server=ctx.guild, role=team_info['team_role'], name=new_name)
            await team_info['team_text'].edit(name=new_name)
            await team_info['team_vc'].edit(name=new_name)
            await team_info['team_cat'].edit(name=new_name)
            emote = "✅"
        else:
            emote = "❌"

        await confirm_msg.reply(emote + ' ' + message)
"""
            

    

@app_commands.command()
@app_commands.describe(team_name="The name of your team.")
@app_commands.describe(member1="A team member.")
@app_commands.describe(member2="A team member.")
@app_commands.describe(member3="A team member.")
@app_commands.describe(member4="A team member.")
@app_commands.describe(member5="A team member.")
async def team(
    interaction: discord.Interaction, 
    team_name: str,
    member1: discord.Member,
    member2: Optional[discord.Member],
    member3: Optional[discord.Member],
    member4: Optional[discord.Member],
    member5: Optional[discord.Member]
):
    '''
    Create a team.
    '''

    members = [m for m in [member1, member2, member3, member4, member5] if m != None]
    logging.info(f"team called with args: team_name={team_name}, members={[m.name for m in members]}")

    # check permissions
    override = False
    if utils.check_perms(interaction.user, config["perms"]["controller"]):
        override = True
        logging.info(f"team: called by Controller, overriding restrictions")

    elif not utils.check_perms(interaction.user, config["perms"]["can_create_team"]):
        logging.info(f"team: ignoring nonpermitted call by {interaction.user}")
        return

    if not override:
        
        # if team creation disabled, exit
        interaction.client.cogs # for some reason, i can only access Teams cog once this has been run.
        team_cog = interaction.client.get_cog("Teams")

        if not team_cog.team_creation_enabled:
            logging.info(f"team: ignoring because team creation is disabled")
            await interaction.response.send_message(f"❌ Your team was not created; team creation is disabled right now.")
            return

        # check run in correct channel
        if not interaction.channel.id == config['channels']['team_create']:
            logging.info(f"team: ignoring because run in wrong channel")
            await interaction.response.send_message(f"❌ Your team was not created; you cannot run this command here.")
            return
    
    # ===== check team name
    
    # check length of name
    if len(team_name) > 100:
        await interaction.response.send_message(f"❌ Your team was not created; your team name is too long. The maximum team name length is 100 characters.")
        return

    # check validity of name
    valid_text_channel = "^([a-z0-9]+-)*[a-z0-9]+$" # valid regex match to something that can be a discord text channel
    if not re.search(valid_text_channel, team_name):
        await interaction.response.send_message(f"❌ Your team was not created; your team name is invalid. Team names may only consist of **lowercase letters** and **digits** separated by **dashes**.\nA few examples of valid team names: `some-team`, `hackathon-winners`, `a-b-c-d-e-f`")
        return
    
    # ensure team name not already taken
    if database.team_exists(team_name):
        await interaction.response.send_message(f"❌ Your team was not created; there is already a team called `{team_name}`.")
        return
    
    # ensure team name won't cause conflicts with anything already in the server
    if dget(interaction.guild.channels, name=team_name) \
        or dget(interaction.guild.categories, name=team_name) \
        or dget(interaction.guild.channels, name=team_name) \
        or dget(interaction.guild.roles, name=team_name):

        await interaction.response.send_message(f"❌ Your team was not created; the name `{team_name}` is not allowed.")
        return
    
    # ===== check team members
    
    # get unique mentions of users for the team members
    for member in members:

        # already disincludes role mentions, need to disinclude bots
        if member.bot:
            await interaction.response.send_message(f"❌ Your team was not created; you cannot have a bot on your team.")
            return

        # ensure user not already in team
        if database.is_on_team(member):
            await interaction.response.send_message(f"❌ Your team was not created; at least one member is already in a team.")
            return
        
        # ensure user is a participant
        for role in member.roles:
            if role.id == config["roles"]["participant"]:
                break
        else:
            await interaction.response.send_message(f"❌ Your team was not created; at least one member does not have the `@participant` role.")
            return
        
    # check for empty team
    if members == []:
        await interaction.response.send_message(f"❌ Your team was not created; you cannot have an empty team!")
        return
    
    # ensure sender is on the team
    if interaction.user not in members and not override: # organizer can create team without restriction
        await interaction.response.send_message(f"❌ Your team was not created; you cannot create a team that you yourself are not on. (Ensure that you are one of the 5 users mentioned in one of the 'member' fields.)")
        return
        
    # ===== team can be created

    msg = "`[Command is being run in override mode.]`" if override else ""
    msg += f"The team `{team_name}` will be created, and members {' '.join([m.mention for m in members])} will be added.\n\n{interaction.user.mention}, please react to this message with ✅ to confirm, or ❌ to cancel."

    await interaction.response.send_message(msg)
    confirm_msg = await interaction.original_response()
    confirmed = await utils.get_confirmation(interaction.client, interaction.user, confirm_msg)

    if confirmed == None: # timed out
        return
    elif confirmed == False: # reacted with ❌
        await confirm_msg.reply(f"Team {team_name} was not created.")
        return
    # otherwise, user confirmed, so we can proceed

    # create team category & role
    team_cat = await interaction.guild.create_category(name=team_name) # category to store team text & vc
    team_role = await interaction.guild.create_role(name=team_name, mentionable=True, colour=config['team_role_colour_obj']) # team role

    # Privatize category so that only team and some others can view
    await team_cat.set_permissions(interaction.guild.default_role, read_messages=False) # @everyone can't view
    await team_cat.set_permissions(team_role, read_messages=True)
    for role_name in ['organizer', 'mentor', 'volunteer', 'sponsor', 'judge']:
        await team_cat.set_permissions(
            dget(interaction.guild.roles, id=config['roles'][role_name]), # get role with ID identified in config
            read_messages=True
        )

    # Create the text and voice channel
    team_text = await interaction.guild.create_text_channel(name=team_name, category=team_cat)
    team_vc = await interaction.guild.create_voice_channel(name=team_name, category=team_cat)
    
    # Add created role to all team members
    for member in members:
        await member.add_roles(team_role)

    # insert team into database
    valid = database.check_team_validity(team_name, team_text, team_vc, team_cat, team_role, members)
    if not valid:
        await confirm_msg.reply(f"❌ Your team was not created because of an unknown problem; paging {utils.get_controller(interaction.guild).mention}.")
        return
    
    database.insert_team(team_name, team_text, team_vc, team_cat, team_role, members)

    # React in confirmation and send notification in team text channel
    await team_text.send(f'Hey {" ".join([member.mention for member in members])}! Here is your team category & channels.')

    logging.info(f"Team created: {team_name}, {[m.name for m in members]}, {team_role}")


def add_team_slash(bot):
    bot.tree.add_command(team, guild=discord.Object(id=config['guild_id']))
