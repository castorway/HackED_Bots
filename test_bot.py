import discord
import os
from dotenv import load_dotenv
import logging

# load env vars like token
load_dotenv()

# bot setup
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# logging setup
log_handler = logging.FileHandler(filename='test_bot.log', encoding='utf-8', mode='w')


@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith('$hello'):
        await message.channel.send('Hello!')

client.run(os.environ['TOKEN'], log_handler=log_handler)