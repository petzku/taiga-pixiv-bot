#!/usr/bin/env python3

import discord

# config, contains secrets
import config

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print('Logged on as', client.user)

if __name__ == "__main__":
    client.run(config.TOKEN)
