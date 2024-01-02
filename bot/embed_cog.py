import discord
from discord.ext import commands
from discord.utils import get as dget
import logging
import utils
import json

args, config = utils.general_setup()


class Embed(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.command(help=f'''Send a custom embed. Restricted.
    
    Usage: {config['prefix']}embed <embed contents>''')
    async def embed(self, ctx, contents: str):
        if not utils.check_perms(ctx.message.author, config["perms"]["controller"]):
            logging.info(f"embed_c: ignoring nonpermitted call by {ctx.message.author.name}")
            return
        
        contents = ctx.message.content.strip(f"{config['prefix']}embed_c ")
        embed = discord.Embed.from_dict(json.loads(contents, strict=False))

        await ctx.send(embed=embed)
        await ctx.message.add_reaction("✅")


    @commands.command(help=f'''Edits a message with a custom embed. Restricted.
    The channel and message ID of the message to be edited must be specified.
    
    Usage: {config['prefix']}embedit <#channel> <message id> <embed contents>''')
    async def embedit(self, ctx, channel: discord.TextChannel, message_id: str):
        if not utils.check_perms(ctx.message.author, config["perms"]["controller"]):
            logging.info(f"embedit_c: ignoring nonpermitted call by {ctx.message.author.name}")
            return

        # embed contents are rest of command after message_id
        contents = ctx.message.content.split(None, 3)[3] 
        embed = discord.Embed.from_dict(json.loads(contents.strip(), strict=False))

        # edit the message
        embed_message = await channel.fetch_message(message_id)
        await embed_message.edit(embed=embed)
        await ctx.message.add_reaction("✅")


    @commands.command(help=f'''Sends a custom embed in a particular channel. Restricted.
    
    Usage: {config['prefix']}embedin <#channel> <embed contents>''')
    async def embedin(self, ctx, channel: discord.TextChannel):
        if not utils.check_perms(ctx.message.author, config["perms"]["controller"]):
            logging.info(f"embedit_c: ignoring nonpermitted call by {ctx.message.author.name}")
            return

        # embed contents are rest of command after channel
        contents = ctx.message.content.split(None, 2)[2] 
        embed = discord.Embed.from_dict(json.loads(contents.strip(), strict=False))

        # edit the message
        await channel.send(embed=embed)
        await ctx.message.add_reaction("✅")


    @commands.command(help=f'''Edits a message with a custom embed, with contents read from a file. Restricted.
    This command is necessary because long/complex embeds will go over the character limit easily.
                      
    Usage: {config['prefix']}embedit_f <#channel> <message id>
    * Message must have a JSON file attached with the embed contents.''')
    async def embedit_f(self, ctx, channel: discord.TextChannel, message_id: str):
        if not utils.check_perms(ctx.message.author, config["perms"]["controller"]):
            logging.info(f"embedit_f: ignoring nonpermitted call by {ctx.message.author.name}")
            return

        # download the attachment
        filename = utils.gen_filename("received_embed", "json")
        with open(filename, "wb") as f:
            await ctx.message.attachments[0].save(fp=f)

        # embed contents are file
        with open(filename, "r") as f:
            contents = f.read()
        
        embed = discord.Embed.from_dict(json.loads(contents.strip(), strict=False))

        # edit the message
        embed_message = await channel.fetch_message(message_id)
        await embed_message.edit(embed=embed)
        await ctx.message.add_reaction("✅")


    @commands.command(help=f'''Sends a custom embed in a particular channel, with contents read from a file. Restricted.
    This command is necessary because long/complex embeds will go over the character limit easily.
                      
    Usage: {config['prefix']}embedin_f <#channel>
    * Message must have a JSON file attached with the embed contents.''')
    async def embedin_f(self, ctx, channel: discord.TextChannel):
        if not utils.check_perms(ctx.message.author, config["perms"]["controller"]):
            logging.info(f"embedin_f: ignoring nonpermitted call by {ctx.message.author.name}")
            return
        
        # download the attachment
        filename = utils.gen_filename("received_embed", "json")
        with open(filename, "wb") as f:
            await ctx.message.attachments[0].save(fp=f)

        # embed contents are file
        with open(filename, "r") as f:
            contents = f.read()

        embed = discord.Embed.from_dict(json.loads(contents.strip(), strict=False))

        # edit the message
        await channel.send(embed=embed)
        await ctx.message.add_reaction("✅")
