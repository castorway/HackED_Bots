import discord
from discord.ext import commands
from discord import app_commands
from discord.utils import get as dget
import logging
import utils
import sheets
import database
from enum import Enum


args, config = utils.general_setup()

class VerifyRes(Enum):
    CAN_BE_VERIFIED = 0
    NOT_REGISTERED = -1
    EMAIL_ALREADY_VERIFIED = -2
    DISCORD_ALREADY_VERIFIED = -3


class Verification(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):

        # contents of all slash commands are ''
        if message.channel.id == config['channels']['verification'] \
            and not message.content == '' \
            and not message.author.bot:

            logging.info(f"illegal message in verification channel: {message.content}")

            # explain to user
            controller = dget(message.guild.members, id=config["controller_id"]) # tell them to direct all problems to the bot controller
            await message.author.send(f"Only messages using the `/verify` command can be sent in the `#verify` channel. If you need help with something and don't have access to the rest of the server, please send a DM to {controller.mention}!")

            # delete message
            await message.delete()


    @commands.command(help=f'''Manually verify a participant (add them to the database and the spreadsheet). Restricted.
    
    Usage: {config['prefix']}manual_verify''')
    async def manual_verify(self, ctx, email: str, first_name: str, last_name: str, discord_id: str):
        '''
        Replicates functionality of /verify slash command, but to be used by an admin just in case of some weird issues.
        '''
        
        logging.info(f"manual_verify called with args: {email}, {first_name}, {last_name}, {discord_id}")

        if not utils.check_perms(ctx.message.author, config["perms"]["controller"]):
            logging.info(f"manual_verify: ignoring nonpermitted call by {ctx.message.author.name}")
            return
        
        # use lowercase for matching to make life easier
        email, first_name, last_name = email.lower(), first_name.lower(), last_name.lower()
                        
        logging.info(f"---- start verify ({email}, {first_name}, {last_name}, {discord_id}) ----")
        res = await check_verifiability(email, first_name, last_name, discord_id)

        # error messages for various error cases
        if res == VerifyRes.NOT_REGISTERED:
            await ctx.reply("There is no registered participant with that information.")
        elif res == VerifyRes.EMAIL_ALREADY_VERIFIED:
            await ctx.reply("A Discord account has already been verified with that email address.")
        elif res == VerifyRes.DISCORD_ALREADY_VERIFIED:
            await ctx.reply("That Discord account has already been verified as a particpant.")

        elif res == VerifyRes.CAN_BE_VERIFIED:
            database.insert_participant(email, first_name, last_name, discord_id) # add to database
            sheets_success = sheets.verify(email, first_name, last_name, discord_id) # check off on registration spreadsheet
            
            if not sheets_success:
                await ctx.reply(f"There was an issue updating the registration spreadsheet.")
            
            else:
                # finally give them the participant role
                user = await ctx.guild.fetch_member(discord_id)
                participant_role = dget(ctx.guild.roles, id=config['roles']['participant'])
                await user.add_roles(participant_role)

                # confirmation message
                await ctx.reply(f"Participant has been verified and given access to the rest of the server.")

        else:
            logging.error(f"Unrecognized VerifyRes code {res}")
            
        logging.info(f"---- end verify ({email}, {first_name}, {last_name}, {discord_id}) ----")



# ========== slash commands to be added in run.py
        
@app_commands.command()
@app_commands.describe(email="The email address you used to sign up.")
@app_commands.describe(first_name="What you put in the 'First Name' field when you signed up.")
@app_commands.describe(last_name="What you put in the 'Last Name' field when you signed up.")
async def verify(interaction: discord.Interaction, email: str, first_name: str, last_name: str):
    '''
    Verify your registration to gain access to the rest of the server.
    '''
    logging.info(f"verify called with args: {email}, {first_name}, {last_name}")

    # ignore any calls outside verification channel
    if interaction.channel.id != config['channels']['verification']:
        logging.info(f"declining nonpermitted call in {interaction.channel.name} outside verification channel")
        await interaction.response.send_message("This command can't be used here!", ephemeral=True)
        return

    # ignore any calls by someone who already has a role
    elif utils.check_perms(interaction.user, config['perms']["cannot_verify_self"]):
        logging.info(f"declining nonpermitted call by user {interaction.user.name}, who has a nonpermitted role")
        await interaction.response.send_message("You cannot use this command!", ephemeral=True)
        return
    
    # use lowercase for matching to make life easier
    email, first_name, last_name = email.lower(), first_name.lower(), last_name.lower()

    # grab this at the start because API calls take a long time and we can't get it from the followup
    discord_id = interaction.user.id

    # sometimes all the db/API queries take a long time; need to defer so the interaction doesn't go away
    await interaction.response.defer(ephemeral=True)

    logging.info(f"---- start verify ({email}, {first_name}, {last_name}, {discord_id}) ----")
    res = await check_verifiability(email, first_name, last_name, discord_id)

    if res == VerifyRes.NOT_REGISTERED:
        await interaction.followup.send(f"We can't find a registrant with that information. Please check your registration form response (a copy was emailed to you on submission) and ensure the email, first name, and last name are *exactly* identical to the values you're entering in the command.")
    elif res == VerifyRes.EMAIL_ALREADY_VERIFIED:
        await interaction.followup.send(f"A Discord account has already been verified using that information.")
    elif res == VerifyRes.DISCORD_ALREADY_VERIFIED:
        await interaction.followup.send(f"You have already verified your Discord account as a different participant.")
    
    elif res == VerifyRes.CAN_BE_VERIFIED:
        
        database.insert_participant(email, first_name, last_name, discord_id) # add to database
        sheets_success = sheets.verify(email, first_name, last_name, discord_id) # check off on registration spreadsheet
        
        if not sheets_success:
            controller = await interaction.guild.fetch_member(config['controller_id'])
            await interaction.followup.send(f"There was an issue confirming your registration; please send a message to {controller.mention}.")
        
        else:
            # finally give them the participant role
            user = dget(interaction.guild.members, id=discord_id)
            participant_role = dget(interaction.guild.roles, id=config['roles']['participant'])
            await user.add_roles(participant_role)

            # confirmation message
            await interaction.followup.send(f"You've been verified and given access to the rest of the server. Welcome to HackED, {first_name.title()}!")

    else:
        logging.error(f"Unrecognized VerifyRes code {res}")

    logging.info(f"---- end verify ({email}, {first_name}, {last_name}, {discord_id}) ----")


async def check_verifiability(email, first_name, last_name, discord_id):
    '''
    Check a participant can be verified. Returns a VerifyRes enum code.
    '''
    
    # make sure information given exactly matches a participant we have registered
    registered = sheets.check_if_registered(email, first_name, last_name)

    if not registered:
        logging.info(f"Participant not registered.")
        return VerifyRes.NOT_REGISTERED
    
    else: # otherwise, need to check database and sheet to make sure account/participant not already *verified*
        
        db_result = database.check_if_verified(email, first_name, last_name, discord_id)
        sheet_result = sheets.check_if_verified(email, first_name, last_name, discord_id)

        # checks for synchronicity
        if db_result != sheet_result:
            logging.error(f"Verification inconsistency between sheet and database for participant ({email}, {first_name}, {last_name}).")
        
        # if participant already verified, don't let em in
        if db_result == "email" or sheet_result == "email":
            logging.info("Participant email already verified.")
            return VerifyRes.EMAIL_ALREADY_VERIFIED
        
        elif db_result == "discord" or sheet_result == "discord":
            logging.info("Discord account already verified.")
            return VerifyRes.DISCORD_ALREADY_VERIFIED
        
        else: # let em in
            logging.info("Participant good to be verified.")
            return VerifyRes.CAN_BE_VERIFIED


def add_verification_slash(bot):
    bot.tree.add_command(verify, guild=discord.Object(id=config['guild_id']))
