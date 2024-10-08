import discord
from discord.ext import commands
from discord import app_commands
from discord.utils import get as dget
from typing import Optional
import logging
import utils
import json
import database
import re

# setup
args, config = utils.general_setup()

with open(config['challenge_data_path'], 'r') as f:
    challenge_data = json.loads(f.read())

def challenge_order(lst):
    return sorted(lst, key=lambda x: challenge_data['challenges'][x]['order'])


class Declare(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.judging_signups_enabled = True


    @commands.command(help=f'''Enables/disables judging signups. Restricted.
    Usage: {config['prefix']}turn_judging_signups [on|off]''')
    async def turn_judging_signups(self, ctx, state: Optional[str]):

        # check permissions
        if not utils.check_perms(ctx.message.author, config["perms"]["controller"]):
            logging.info(f"turn_judging_signups: ignoring nonpermitted call by {ctx.message.author.name}")
            return

        if state == "on":
            self.judging_signups_enabled = True
            await ctx.message.add_reaction("✅")
            await ctx.message.reply(f'Judging signups enabled.')

        elif state == "off":
            self.judging_signups_enabled = False
            await ctx.message.add_reaction("✅")
            await ctx.message.reply(f'Judging signups disabled.')

        else:
            await ctx.message.add_reaction("❌")
            await ctx.reply(f"Something was wrong with your command. This command can be run either as `~turn_team_creation on` or `~turn_team_creation off`.")


@app_commands.command()
@app_commands.choices(challenge1=[app_commands.Choice(name=c, value=c) for c in challenge_data['optional_challenges']])
@app_commands.choices(challenge2=[app_commands.Choice(name=c, value=c) for c in challenge_data['optional_challenges']])
async def judging_signup(
    interaction: discord.Interaction,
    challenge1: Optional[app_commands.Choice[str]],
    challenge2: Optional[app_commands.Choice[str]],
    github_link: str,
    devpost_link: str
):
    '''
    Sign up your team for judging, declare your challenge/s, and submit your project links.
    '''

    medium_pref = "" # last-minute getting rid of this

    logging.info(f"judging_signup called with args: challenge1={challenge1}, challenge2={challenge2}, medium_pref={medium_pref}, github_link={github_link}, devpost_link={devpost_link}")

    # check permissions
    if not utils.check_perms(interaction.user, config["perms"]["can_create_team"]):
        logging.info(f"judging_signup: ignoring nonpermitted call by {interaction.user}")
        return
    
    # check run in a team's channel
    team_name = database.team_from_text_channel(interaction.channel.id)
    logging.info(f"judging_signup: team {team_name} signing up")
    if team_name == None:
        logging.info(f"judging_signup: ignoring because channel_id not associated with team")
        await interaction.response.send_message(f"❌ You cannot run this command here.", ephemeral=True) # ephemeral message so as to not make command public
        return

    # if signups disabled, exit
    interaction.client.cogs
    chal_cog = interaction.client.get_cog("Declare")

    if not chal_cog.judging_signups_enabled:
        logging.info(f"judging_signup: ignoring because signups are disabled")
        await interaction.response.send_message(f"❌ Your team was not signed up for judging; judging signups are disabled right now.")
        return

    # validate links just a little bit
    if re.search(".*github.com.*", github_link) == None:
        await interaction.response.send_message(f"❌ Your team was not signed up for judging; it looks like your GitHub link isn't a proper link to a repository.")
        return
        
    if re.search(".*devpost.com.*", devpost_link) == None:
        await interaction.response.send_message(f"❌ Your team was not signed up for judging; it looks like your DevPost link isn't a proper link to a DevPost project.")
        return
    
    # order challenges in standard way
    # only unique, non-None challenges
    new_challenges = challenge_order(list(set([c.name for c in [challenge1, challenge2] if c != None])))
    old_challenges = challenge_order(database.get_teams_challenges(team_name))
    logging.info(f"judging_signup: old challenges: {old_challenges}, new_challenges: {new_challenges} before adding HackED")

    # info about old challenges
    msg1 = "## Challenges\n"
    if old_challenges:
        msg1 += f"Before you ran this command, `{team_name}` was signed up for:\n"
        msg1 += '\n'.join([f"- {challenge_data['challenges'][x]['formatted_name']}" for x in old_challenges])
        msg1 += '\n'
    else:
        msg1 += f"Before you ran this command, `{team_name}` was not signed up for judging.\n\n"
        
    # check any combinations of 2 are ok
    if len(new_challenges) > 1 and new_challenges not in challenge_data['accepted_combinations']:
        await interaction.response.send_message(f"❌ Your team was not signed up for judging; that combination of challenges is not allowed.")
        return
    
    # now can add main hacked as a "challenge" by default; put at beginning so it is printed first
    new_challenges.insert(0, challenge_data['main_challenge'])
    
    # can actually sign up for challenges yay
    success = database.modify_team_challenges(team_name, new_challenges)
    if not success:
        controller = await utils.get_controller(interaction.guild)
        await interaction.response.send_message(f"❌ Your team was not fully signed up for judging; something unknown went wrong. Paging {controller.mention}.")
        return
    
    # register medium pref, github/devpost links
    success = database.modify_team_judging_info(team_name, medium_pref, github_link, devpost_link)
    if not success:
        controller = await utils.get_controller(interaction.guild)
        await interaction.response.send_message(f"❌ Your team was not fully signed up for judging; something unknown went wrong. Paging {controller.mention}.")
        return

    # info about new challenges
    msg1 += f"Now, `{team_name}` is signed up for:\n"
    msg1 += '\n'.join([f"- {challenge_data['challenges'][x]['formatted_name']}\n  - {challenge_data['challenges'][x]['additional_info']}" for x in new_challenges])
    msg1 += "\nPlease review the rules for any challenges you have signed up for in <#1187246978535530506> and ensure your team meets all challenge requirements."

    # info about medium pref, github/devpost links
    # msg2 = "### Medium Preference:\n"
    # msg2 += f"- Your medium preference is `{medium_pref}`.\n"
    # msg2 += f"- This means we will *try* to match you with {medium_pref} judges for the best experience. Any judges can judge online/in-person teams; you will be able to present regardless of the judges you are put with, so don't worry about this."

    msg3 = "## GitHub & DevPost:\n"
    msg3 += f"- Your GitHub link is: `{github_link}`\n"
    msg3 += f"- Your DevPost link is: `{devpost_link}`\n"
    msg3 += f"- It's okay to submit an empty/template GitHub/DevPost early on, but **make sure your GitHub and DevPost are up-to-date** with your **full project code and information** by the Hacking End Time.\n"
    msg3 += f"- **Make sure your GitHub repository is public.**\n"
    msg3 += f"- **Make sure your DevPost project was submitted *to [the HackED 2024 DevPost](https://hacked-2024.devpost.com/)*.**\n"
    msg3 += f"- See the [GitHub & DevPost Details](https://discord.com/channels/1179492116334919710/1179497189765038191/1190362760920449095) for specific requirements.\n\n"

    msg4 = "## More Information:\n"
    msg4 += "- Check the [Judging Signup Details](https://discord.com/channels/1179492116334919710/1179497189765038191/1190362788745445436) for more information on this command.\n"
    msg4 += "*Please review the above information and ensure you understand it all.* You are free to change any of this by rerunning `/judging_signup` with updated information **until the Hacking End Time**. You may also run `/judging_withdraw` to withdraw your team from judging.\n"

    # send first message
    await interaction.response.send_message(msg1)
    # send remaining messages in channel
    # await interaction.channel.send(msg2)
    await interaction.channel.send(msg3)
    await interaction.channel.send(msg4)


@app_commands.command()
async def judging_withdraw(interaction: discord.Interaction):
    '''
    Withdraw your team from judging.
    '''
    logging.info(f"judging_withdraw called")

    # check permissions
    if not utils.check_perms(interaction.user, config["perms"]["can_create_team"]):
        logging.info(f"judging_withdraw: ignoring nonpermitted call by {interaction.user}")
        return
    
    # check run in a team's channel
    team_name = database.team_from_text_channel(interaction.channel.id)
    logging.info(f"judging_withdraw: team {team_name} signing up")
    if team_name == None:
        logging.info(f"judging_withdraw: ignoring because channel_id not associated with team")
        await interaction.response.send_message(f"❌ You cannot run this command here.", ephemeral=True) # ephemeral message so as to not make command public
        return

    # if signups disabled, exit
    interaction.client.cogs
    chal_cog = interaction.client.get_cog("Declare")

    if not chal_cog.judging_signups_enabled:
        logging.info(f"judging_withdraw: ignoring because signups are disabled")
        await interaction.response.send_message(f"❌ Your team was not withdrawn from judging; judging signups are disabled right now.")
        return

    # can actually sign up for challenges yay
    success = database.modify_team_challenges(team_name, [])
    if not success:
        await interaction.response.send_message(f"❌ Your team was not fully withdrawn from judging; something unknown went wrong. Paging {utils.get_controller(interaction.message.guild).mention}.")
        return
    
    # register medium pref, github/devpost links
    success = database.modify_team_judging_info(team_name, None, None, None)
    if not success:
        await interaction.response.send_message(f"❌ Your team was not fully withdrawn from judging; something unknown went wrong. Paging {utils.get_controller(interaction.message.guild).mention}.")
        return
    
    await interaction.response.send_message(f"**`{team_name}` was withdrawn from judging.** This means you are now **not eligible for any prizes** and you do not have to present your project for judging. If you change your mind, you can run the `/judging_signup` command to sign up for judging **at any point before the Hacking End Time**.")


def add_declare_slash(bot):
    bot.tree.add_command(judging_signup, guild=discord.Object(id=config['guild_id']))
    bot.tree.add_command(judging_withdraw, guild=discord.Object(id=config['guild_id']))
