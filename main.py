#!/usr/bin/env python3

from typing import List

import discord
import re
import math
from os import path, makedirs
from sys import stderr

import pixivpy3
import requests
import pixiv_auth

# config, contains secrets
import config

pixiv_re = re.compile(
    r"(?<!<)https?://(?:www\.)?pixiv\.net/(?:.*artworks/(?P<new_id>\d+)|member_illust\.php\?.*illust_id=(?P<old_id>\d+))(?:[^\s>]*#(?P<img_n>\d+))?(?!\S*>)",
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


def pixiv_req(method, url, **kwargs):
    headers = {"Referer": "https://app-api.pixiv.net/"}
    return requests.request(method, url=url, headers=headers, **kwargs)


def is_over_8mb(url):
    return int(pixiv_req("HEAD", url).headers["Content-Length"]) >= 8388284


def select_reasonable_url(original_url, large_url):
    # if is_over_8mb(original_url):
    #     # the "large" URL from the API is actually a 600px one, not 1200px
    #     return large_url.replace("c/600x1200_90/", "")
    return original_url


def is_spoilered(content: str, linkstart: int, linkend: int):
    """figure out if the link is spoilered

    Scans the start of the string to identify if there is an unclosed spoiler,
    i.e. an uneven number of `||` pairs, and the end to identify if there is a closing one at all.
    """
    before = len(spoiler_re.findall(content, endpos=linkstart))
    after = spoiler_re.search(content, pos=linkend)
    return before % 2 == 1 and after is not None


async def send_embeds(message: discord.Message):
    for match in pixiv_re.finditer(message.content):
        pid = match.group("new_id") or match.group("old_id")
        img_n = match.group("img_n")
        nth_image_message = ""
        details = api_auth_wrapper(api.illust_detail, int(pid)).illust
        if details.meta_single_page:
            urls = [
                select_reasonable_url(
                    details.meta_single_page.original_image_url,
                    details.image_urls.large,
                )
            ]
        elif pages := details.meta_pages:
            urls = [
                select_reasonable_url(page.image_urls.original, page.image_urls.large)
                for page in pages
            ]
            if img_n and 0 <= (n := int(img_n) - 1) < len(urls):
                nth_image_message = f"Image {n+1} of {len(urls)}"
                urls = urls[n : n + 1]
        else:
            continue
        should_spoiler = is_spoilered(message.content, match.start(), match.end())

        # add reaction to indicate to user "work in progress"; removed after done
        await message.add_reaction("🕓")

        # before downloading, ensure temp directory exists
        if not path.exists(config.TEMPDIR):
            makedirs(config.TEMPDIR)
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
            await message.reply(
                content=nth_image_message, files=files, mention_author=False
            )
    # remove embeds from invoking message
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


def allow_unspoiler(message: discord.Message):
    # on some servers, we want to allow replies to anything instead of only spoilered messages.
    # allow management either on server or channel basis.
    if message.channel.id in config.ONLY_SPOILER:
        return not config.ONLY_SPOILER[message.channel.id]
    if message.guild and message.guild.id in config.ONLY_SPOILER:
        return not config.ONLY_SPOILER[message.guild.id]
    return True


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
        and (allow_unspoiler(message) or has_spoiler(message))
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
