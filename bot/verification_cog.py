import discord
from discord.ext import commands
from discord import app_commands
from discord.utils import get as dget
import logging
import utils
import sheets

args, config = utils.general_setup()

class Verification(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # @commands.Cog.listener()
    # async def on_raw_reaction_add(self, reaction):
    #     """
    #     Called whenever a reaction is added to a message. Checks if the message is the verification message, and
    #     sends DMs to the user appropriately to prompt for verification.
    #     """
    #     print("react!", reaction)

    #     # check the reaction is for verification purposes; to correct message with correct emote
    #     if reaction.channel_id == config["verification_channel_id"] \
    #         and reaction.message_id == config["verification_message_id"] \
    #         and reaction.emoji.name == "⭐":

    #         logging.info(f"{reaction.member.name} reacted to verification message")

    #         channel = self.bot.get_channel(reaction.channel_id) # get verification channel
    #         await channel.send("hey bestie", ephemeral=True)

    #     else:
    #         logging.info(f"react not to verification message: {reaction.emoji}, channel={reaction.channel_id}, message={reaction.message_id}")


# ========== slash commands to be added in run.py
        
@app_commands.command()
@app_commands.describe(email="The email address you used to sign up.")
@app_commands.describe(first_name="What you put in the 'First Name' field when you signed up.")
@app_commands.describe(last_name="What you put in the 'Last Name' field when you signed up.")
async def verifyme(interaction: discord.Interaction, email: str, first_name: str, last_name: str):
    logging.info(f"verifyme called with args: {interaction}, {email}, {first_name}, {last_name}")
    # email, name = ctx.message.content.split(limit=3)[1:]

    registered = sheets.check_if_registered(email, first_name, last_name)
    logging.info(f"registered: {registered}")

    if not registered:
        # denial message
        controller = dget(interaction.guild.members, id=config["controller_id"]) # tell them to direct all problems to the bot controller
        await interaction.response.send_message(f" We can't find a registrant with that information. Please check your registration form response (a copy was emailed to you on submission) and ensure the email, first name, and last name are *exactly* identical to the values you're entering in the command (it is case-sensitive!). Send {controller.mention} a DM if you're still having trouble.", ephemeral=True)
        return

    # otherwise, need to check database...
        
    await interaction.response.send_message("success message placeholder", ephemeral=True)



def add_verification_slash(bot):
    bot.tree.add_command(verifyme, guild=discord.Object(id=config['guild_id']))