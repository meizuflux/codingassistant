import difflib
import io
import os
import re
import zlib
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote_plus

import discord
from bs4 import BeautifulSoup
from discord.ext import commands

NOTHING_FOUND = "Sorry, I couldn't find anything for that query."


@dataclass
class Docs:
    url: str
    lang: str
    aliases: Optional[tuple] = None
    method: int = 0


async def from_rust(ctx, url, text):
    def soup_match(tag):
        return all(string in tag.text for string in text.strip().split()) and tag.name == 'li'

    async with ctx.bot.session.get(parse_url(url)) as resp:
        soup = BeautifulSoup(str(await resp.text()), 'lxml')
    e = [x.select_one("li > a") for x in soup.find_all(soup_match, limit=8)]
    links = [link for link in e if link is not None]
    if not links:
        await ctx.send(NOTHING_FOUND)
        return
    lines = [f"[`{a.string}`](https://doc.rust-lang.org/std/{a.get('href')})" for a in e]
    await ctx.send(embed=format_embed(lines))


async def c_or_cpp(ctx, url, text, lang):
    async with ctx.bot.session.get(parse_url(url + "?title=Special:Search&search=" + text)) as resp:
        soup = BeautifulSoup(str(await resp.text()), 'lxml')

    results = soup.find_all('ul', class_='mw-search-results')
    if not len(results):
        await ctx.send(NOTHING_FOUND)
        return
    links = results[0 if lang == "c++" else 1].find_all('a', limit=8)
    lines = [f"[`{a.string}`](https://en.cppreference.com/{a.get('href')})" for a in links]
    await ctx.send(embed=format_embed(lines))


async def from_c(ctx, url, text):
    await c_or_cpp(ctx, url, text, lang="c")


async def from_cpp(ctx, url, text):
    await c_or_cpp(ctx, url, text, lang="c++")


def parse_url(url):
    return quote_plus(url, safe=';/?:@&=$,><-[]')


def format_embed(lines):
    e = discord.Embed(colour=discord.Colour.blurple())
    e.description = "\n".join(lines)
    return e


class SphinxObjectFileReader:
    # Inspired by Sphinx's InventoryFileReader
    BUFSIZE = 16 * 1024

    def __init__(self, buffer):
        self.stream = io.BytesIO(buffer)

    def readline(self):
        return self.stream.readline().decode('utf-8')

    def skipline(self):
        self.stream.readline()

    def read_compressed_chunks(self):
        decompressor = zlib.decompressobj()
        while True:
            chunk = self.stream.read(self.BUFSIZE)
            if len(chunk) == 0:
                break
            yield decompressor.decompress(chunk)
        yield decompressor.flush()

    def read_compressed_lines(self):
        buf = b''
        for chunk in self.read_compressed_chunks():
            buf += chunk
            pos = buf.find(b'\n')
            while pos != -1:
                yield buf[:pos].decode('utf-8')
                buf = buf[pos + 1:]
                pos = buf.find(b'\n')


class RTFM(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._valid_docs = {
            "discord.py": Docs(
                url="https://discordpy.readthedocs.io/en/latest",
                aliases=("d.py",),
                lang="python"
            ),
            "python": Docs(
                url="https://docs.python.org/3",
                aliases=("py",),
                lang="python"
            ),
            "zaneapi": Docs(
                url="https://docs.zaneapi.com/en/latest",
                aliases=("zane",),
                lang="API"
            ),
            "pillow": Docs(
                url="https://pillow.readthedocs.io/en/stable",
                aliases=("pil",),
                lang="python"
            ),
            "asyncpg": Docs(
                url="https://magicstack.github.io/asyncpg/current",
                lang="python"
            ),
            "aiohttp": Docs(
                url="https://docs.aiohttp.org/en/stable",
                lang="python"
            ),
            "wand": Docs(
                url="https://docs.wand-py.org/en/0.6.5",
                lang="python"
            ),
            "numpy": Docs(
                url="https://numpy.org/doc/1.20",
                aliases=('np',),
                lang="python"
            ),
            "rust": Docs(
                url="https://doc.rust-lang.org/std/all.html",
                method=1,
                aliases=('rs',),
                lang="Rust"
            ),
            "beautifulsoup": Docs(
                url="https://www.crummy.com/software/BeautifulSoup/bs4/doc",
                aliases=('bs4', 'beautifulsoup4'),
                lang="python"
            ),
            "flask": Docs(
                url="https://flask.palletsprojects.com/en/1.1.x",
                lang="python"
            ),
            "pymongo": Docs(
                url="https://pymongo.readthedocs.io/en/stable",
                lang="python"
            ),
            "yarl": Docs(
                url="https://yarl.readthedocs.io/en/latest",
                lang="python"
            ),
            "requests": Docs(
                url="https://docs.python-requests.org/en/master",
                lang="python"
            ),
            "selenium-py": Docs(
                url="https://www.selenium.dev/selenium/docs/api/py",
                lang="python",
                aliases=('selenium-python',)
            ),
            "pandas": Docs(
                url="https://pandas.pydata.org/pandas-docs/stable",
                lang="python"
            ),
            "pygame": Docs(
                url="https://www.pygame.org/docs",
                lang="python"
            ),
            "matplotlib": Docs(
                url="https://matplotlib.org/stable",
                lang="python"
            ),
            "c": Docs(
                url="https://cppreference.com/w/c/index.php",
                lang="c",
                method=1
            ),
            "cpp": Docs(
                url="https://cppreference.com/w/cpp/index.php",
                lang="c++",
                aliases=('c++',),
                method=1
            ),
            "sqlalchemy": Docs(
                url="https://docs.sqlalchemy.org/en/14",
                lang="python"
            )
        }
        self.rtfm_cache = {item: {} for item in self.valid_doc_urls}

    @property
    def valid_doc_urls(self):
        return {name: data.url for name, data in self._valid_docs.items()}

    def parse_object_inv(self, stream, url):
        # key: URL
        # n.b.: key doesn't have `discord` or `discord.ext.commands` namespaces
        result = {}

        # first line is version info
        inv_version = stream.readline().rstrip()

        if inv_version != '# Sphinx inventory version 2':
            raise RuntimeError('Invalid objects.inv file version.')

        # next line is "# Project: <name>"
        # then after that is "# Version: <version>"
        projname = stream.readline().rstrip()[11:]
        version = stream.readline().rstrip()[11:]

        # next line says if it's a zlib header
        line = stream.readline()
        if 'zlib' not in line:
            raise RuntimeError('Invalid objects.inv file, not z-lib compatible.')

        # This code mostly comes from the Sphinx repository.
        entry_regex = re.compile(r'(?x)(.+?)\s+(\S*:\S*)\s+(-?\d+)\s+(\S+)\s+(.*)')
        for line in stream.read_compressed_lines():
            match = entry_regex.match(line.rstrip())
            if not match:
                continue

            name, directive, prio, location, dispname = match.groups()
            domain, _, subdirective = directive.partition(':')
            if directive == 'py:module' and name in result:
                # From the Sphinx Repository:
                # due to a bug in 1.1 and below,
                # two inventory entries are created
                # for Python modules, and the first
                # one is correct
                continue

            # Most documentation pages have a label
            if directive == 'std:doc':
                subdirective = 'label'

            if location.endswith('$'):
                location = location[:-1] + name

            key = name if dispname == '-' else dispname
            prefix = f'{subdirective}:' if domain == 'std' else ''

            if projname == 'discord.py':
                key = key.replace('discord.ext.commands.', '').replace('discord.', '')

            result[f'{prefix}{key}'] = os.path.join(url, location)

        return result

    async def build_rtfm_lookup_table(self, page_types):
        cache = {}
        for key, page in page_types.items():
            async with self.bot.session.get(page + '/objects.inv') as resp:
                if resp.status != 200:
                    raise RuntimeError('Cannot build rtfm lookup table, try again later.')

                stream = SphinxObjectFileReader(await resp.read())
                cache[key] = self.parse_object_inv(stream, page)

        self.rtfm_cache = cache

    async def build_table(self, key):
        url = self.valid_doc_urls[key]
        async with self.bot.session.get(url + '/objects.inv') as resp:
            if resp.status != 200:
                raise RuntimeError('Cannot build rtfm lookup table, try again later.')

            stream = SphinxObjectFileReader(await resp.read())
            self.rtfm_cache[key] = self.parse_object_inv(stream, url)

    async def from_sphinx(self, ctx, key, obj):
        if not self.rtfm_cache[key]:
            await ctx.trigger_typing()
            await self.build_table(key)

        cache = self.rtfm_cache[key]

        matches = difflib.get_close_matches(obj, cache, cutoff=0.2)

        if len(matches) == 0:
            return await ctx.send(NOTHING_FOUND)

        await ctx.send(embed=format_embed([f'[`{match}`]({cache[match]})' for match in matches]))

    async def do_rtfm(self, ctx, key, obj):
        if obj is None:
            await ctx.send(self.valid_doc_urls[key])
            return

        method = self._valid_docs[key].method
        if method == 0:
            await self.from_sphinx(ctx, key, obj)
        if method == 1:
            await globals()['from_' + key](ctx, self.valid_doc_urls[key], obj)

    def get_key(self, query):
        for key, value in self._valid_docs.items():
            if key == query:
                return key
            if aliases := value.aliases:
                if query in aliases:
                    return key

    @property
    def valid_docs(self):
        items = [name for name in self._valid_docs]
        for doc in self._valid_docs.values():
            if not doc.aliases:
                continue
            items.extend(doc.aliases)
        return items

    @commands.group(
        invoke_without_command=True,
        aliases=('doc', 'documentation', 'docs', 'rtfs', 'rtm')
    )
    async def rtfm(self, ctx, documentation, *, query=None):
        """Sends documentation based on an entity."""
        if documentation not in self.valid_docs:
            await self.valid(ctx)
            return
        await self.do_rtfm(ctx, key=self.get_key(documentation), obj=query)

    @rtfm.command()
    async def valid(self, ctx):
        embed = discord.Embed(color=discord.Color.red())
        embed.title = "These are the valid items you can query for documentation."
        embed.description = "Note that some may share the same results.\n`" + "`, `".join(self.valid_docs) + "`"
        await ctx.send(embed=embed)
