#!/usr/bin/env python3

from typing import List

import discord
import re
import math
from os import path

import pixivpy3

# config, contains secrets
import config

pixiv_re = re.compile(
    r"https?:\/\/(?:www\.)?pixiv\.net\/(?:.*artworks\/(?P<new_id>\d+)|member_illust\.php\?.*illust_id=(?P<old_id>\d+))\/?",
    re.IGNORECASE,
)
spoiler_re = re.compile(r"(?<!\\)\|\|")

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

api = pixivpy3.AppPixivAPI()


@client.event
async def on_ready():
    print("Logged on as", client.user)


def is_spoilered(content: str, linkstart: int, linkend: int):
    """figure out if the link is spoilered"""
    before = len(spoiler_re.findall(content, endpos=linkstart))
    after = len(spoiler_re.findall(content, pos=linkend))
    return before % 2 == 1 and after > 0


async def send_embeds(message: discord.Message):
    for match in pixiv_re.finditer(message.content):
        pid = match.group("new_id") or match.group("old_id")
        details = api.illust_detail(int(pid)).illust
        if details.meta_single_page:
            urls = [details.image_urls.large]
        elif pages := details.meta_pages:
            urls = [page.image_urls.large for page in pages]
        else:
            continue
        should_spoiler = is_spoilered(message.content, match.start(), match.end())
        for i in range(math.ceil(len(urls) / 10)):
            # limit is 10 attachments per message
            files: List[discord.File] = []
            for url in urls[i * 10 : (i + 1) * 10]:
                fname = url.split("/")[-1]
                api.download(url, path=config.TEMPDIR)
                files.append(
                    discord.File(
                        path.join(config.TEMPDIR, fname), spoiler=should_spoiler
                    )
                )
            await message.reply(files=files, mention_author=False)


def has_pixiv_link(message: discord.Message):
    return "pixiv.net/" in message.content


def has_spoiler(message: discord.Message):
    return bool(spoiler_re.search(message.content))


def is_accepted_channel(message: discord.Message):
    if config.CHANNELS:
        return message.channel.id in config.CHANNELS
    if config.SERVERS:
        return message.guild.id in config.SERVERS
    # if neither whitelist exists, accept all
    return True


@client.event
async def on_message(message: discord.Message):
    # don't respond to ourselves
    if message.author == client.user:
        return

    if (
        is_accepted_channel(message)
        and has_pixiv_link(message)
        and has_spoiler(message)
    ):
        await send_embeds(message)


if __name__ == "__main__":
    api.set_auth(config.PIXIV_TOKEN)
    client.run(config.TOKEN)
