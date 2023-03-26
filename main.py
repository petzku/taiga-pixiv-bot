#!/usr/bin/env python3

from typing import List

import discord
import re
import math
from os import path

import pixivpy3
import pixiv_auth

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
        details = api_auth_wrapper(api.illust_detail, int(pid)).illust
        if details.meta_single_page:
            urls = [details.image_urls.large]
        elif pages := details.meta_pages:
            urls = [page.image_urls.large for page in pages]
        else:
            continue
        should_spoiler = is_spoilered(message.content, match.start(), match.end())

        await message.add_reaction("🕓")

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
    try:
        await message.edit(suppress=True)
    except discord.errors.Forbidden:
        pass
    if client.user:  # to make mypy happy -- we will always be logged in here
        await message.remove_reaction("🕓", (client.user))


def has_pixiv_link(message: discord.Message):
    return "pixiv.net/" in message.content


def has_spoiler(message: discord.Message):
    return bool(spoiler_re.search(message.content))


def is_accepted_channel(message: discord.Message):
    # if guild is not defined, we're in a DM
    if message.guild and config.ALLOWLIST:
        if message.guild.id not in config.ALLOWLIST:
            return False
        if not (channellist := config.ALLOWLIST[message.guild.id]):
            # list is empty => allow any channel
            return True
        # otherwise, check that the current channel is on the accept list
        return message.channel.id in channellist
    # if allowlist is empty, or in DM, accept everything
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


# auth stuff


def read_auth_from_file():
    with open(config.AUTHFILE, "r") as fo:
        access = fo.readline().strip().split()[-1]
        refresh = fo.readline().strip().split()[-1]
    return access, refresh


def authenticate_api():
    access, _ = read_auth_from_file()
    api.set_auth(access)


def refresh_auth():
    _, refresh = read_auth_from_file()
    access, _ = pixiv_auth.refresh(refresh)
    api.set_auth(access)


def api_auth_wrapper(func, *args, **kwargs):
    res = func(*args, **kwargs)
    if not res.error:
        return res
    print("error, refreshing...")
    # if error: refresh auth, then try again
    try:
        refresh_auth()
    except pixiv_auth.RefreshError:
        print("Error refreshing auth token!", file=stderr)
    return func(*args, **kwargs)


if __name__ == "__main__":
    authenticate_api()
    client.run(config.TOKEN)
