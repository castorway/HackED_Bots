import discord
from discord.ext import commands
from discord import app_commands
from discord.utils import get as dget
import logging
import utils
import sheets
import database

args, config = utils.general_setup()

class Verification(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):

        # contents of all slash commands are ''
        if message.channel.id == config['channels']['verification'] \
            and not message.content == '':

            logging.info(f"illegal message in verification channel: {message.content}")

            # explain to user
            controller = dget(message.guild.members, id=config["controller_id"]) # tell them to direct all problems to the bot controller
            await message.author.send(f"Only messages using the `/verify` command can be sent in the `#verify` channel. If you need help with something and don't have access to the rest of the server, please send a DM to {controller.mention}!")

            # delete message
            await message.delete()


# ========== slash commands to be added in run.py
        
@app_commands.command()
@app_commands.describe(email="The email address you used to sign up.")
@app_commands.describe(first_name="What you put in the 'First Name' field when you signed up.")
@app_commands.describe(last_name="What you put in the 'Last Name' field when you signed up.")
async def verify(interaction: discord.Interaction, email: str, first_name: str, last_name: str):
    '''
    Check presence in database and spreadsheet, verify user based on email/name. Notify them and set
    their roles as appropriate.
    '''

    logging.info(f"verify called with args: {email}, {first_name}, {last_name}")

    # grab this at the start because API calls take a long time and we can't get it from the followup
    discord_id = interaction.user.id

    # sometimes all the db/API queries take a long time; need to defer so the interaction doesn't go away
    await interaction.response.defer(ephemeral=True)

    # use lowercase for name matching to make life easier
    first_name, last_name = first_name.lower(), last_name.lower()

    logging.info(f"---- start verify ({email}, {first_name}, {last_name}) ----")

    # make sure information given exactly matches a participant we have registered
    registered = sheets.check_if_registered(email, first_name, last_name)
    logging.info(f"Participant registered: {registered}")

    if not registered:
        controller = dget(interaction.guild.members, id=config["controller_id"]) # tell them to direct all problems to the bot controller
        await interaction.followup.send(f"We can't find a registrant with that information. Please check your registration form response (a copy was emailed to you on submission) and ensure the email, first name, and last name are *exactly* identical to the values you're entering in the command. Send {controller.mention} a DM if you're still having trouble.")
        return
    
    # otherwise, need to check database and sheet to make sure account/participant not already *verified*
    
    db_result = database.check_if_verified(email, first_name, last_name, discord_id)
    sheet_result = sheets.check_if_verified(email, first_name, last_name, discord_id)

    # checks for synchronicity
    if db_result != sheet_result:
        logging.error(f"Verification inconsistency between sheet and database for participant ({email}, {first_name}, {last_name}).")
    
    # if participant already verified, don't let em in
    if db_result == "email" or sheet_result == "email":
        logging.info("Participant email already verified.")
        await interaction.followup.send(f"A Discord account has already been verified using that information.")
    
    elif db_result == "discord" or sheet_result == "discord":
        logging.info("Discord account already verified.")
        await interaction.followup.send(f"You have already verified your Discord account as a different participant.")
    
    else:
        # add to database
        database.insert_participant(email, first_name, last_name, discord_id)

        # check off on registration spreadsheet
        sheets.verify(email, first_name, last_name, discord_id)

        # finally give them the role
        user = dget(interaction.guild.members, id=discord_id)
        participant_role = dget(interaction.guild.roles, id=config['roles']['participant'])
        await user.add_roles(participant_role)

        await interaction.followup.send(f"You've been verified and given access to the rest of the server. Welcome to HackED, {first_name.title()}!")
    
    logging.info(f"---- end verify ({email}, {first_name}, {last_name}) ----")
    

def add_verification_slash(bot):
    bot.tree.add_command(verify, guild=discord.Object(id=config['guild_id']))