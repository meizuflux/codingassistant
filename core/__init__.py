import asyncio
from typing import Any

import aiohttp
import discord
import toml
from discord.ext import commands

class Context(commands.Context):
    async def mystbin(self, data: Any):
        data = bytes(str(data), 'utf-8')
        async with self.bot.session.post('https://mystb.in/documents', data=data) as r:
            res = await r.json()
            key = res["key"]
            return f"https://mystb.in/{key}"


class Bot(commands.AutoShardedBot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # core
        self.loop = asyncio.get_event_loop()
        self.cwd = "D:/coding/Coder/"
        with open(self.cwd + "config.toml") as config:
            self.settings = toml.loads(config.read())

        self.loop.create_task(self.__asyncinit__())

    async def __asyncinit__(self):
        headers = {
            "User-agent": "CodingAssistant Discord bot created by ppotatoo#9688. discord.py version " + discord.__version__
        }
        self.session = aiohttp.ClientSession(headers=headers)

    def run(self):
        self.load_extensions()
        super().run(self.settings['core']['token'])

    def load_extensions(self):
        extensions = (
            'jishaku',
            'extensions.code',
            'extensions.misc'
        )
        for ext in extensions:
            self.load_extension(ext)

    async def on_ready(self):
        print("Connected to Discord.")

    async def get_context(self, message, *, cls=Context):
        return await super().get_context(message, cls=cls)





