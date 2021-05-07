import difflib
from dataclasses import dataclass
from traceback import format_exception
from typing import Optional
from urllib.parse import quote_plus

import discord
from bs4 import BeautifulSoup
from discord.ext import commands
from requests_html import AsyncHTMLSession

from extensions.code.func import SphinxObjectFileReader, parse_object_inv

NOTHING_FOUND = "Sorry, I couldn't find anything for that query."


@dataclass
class Docs:
    url: str
    lang: str
    aliases: Optional[tuple] = None
    method: int = 0
    _type: str = "Package/Library"
    doc_url: str = None

    @property
    def type(self):
        return self._type


class WebScrapeRTFM:
    def __init__(self, bot, docs: iter):
        self.bot = bot
        self.cache = {doc: {} for doc in docs}

    async def discordjs(self, ctx, url, query):
        async with ctx.bot.session.get(self.parse_url(url + query)) as resp:
            if not resp.ok:
                await ctx.send(f"Looks like something went wrong here. HTTP Code {resp.status}")
            data = await resp.json()
            if not data:
                await ctx.send(NOTHING_FOUND)
                return
            results = data['description'].split("\n")[:8]
            lines = []
            for result in results:
                result = result.split(": **[", maxsplit=1)[1]
                split_ = result.strip("*").split("](")
                lines.append(f'[`{split_[0]}`]({split_[1].rstrip(")")})')

            await ctx.send(embed=format_embed(lines))
            self.cache['discordjs'][query] = lines

    async def rust(self, ctx, url, query):
        url = self.parse_url(url + query)
        sess = AsyncHTMLSession()
        r = await sess.get(url)
        await r.html.arender()
        try:
            results = r.html.find('.search-results')[0].find('tr')
        except IndexError:
            await ctx.send(NOTHING_FOUND)
            return
        lines = []
        for i in results[:8]:
            td = i.find('td', first=True)
            links = "https://doc.rust-lang.org/" + td.find('a')[0].attrs['href'].replace('..', '')
            spans = td.find('span')
            name = ''.join(i.text for i in spans)
            lines.append(f"[{name}]({links})")

        await ctx.send(embed=format_embed(lines))
        self.cache['rust'][query] = lines
        await sess.close()

    async def c_or_cpp(self, ctx, url, text, lang):
        async with ctx.bot.session.get(self.parse_url(url + "?title=Special:Search&search=" + text)) as resp:
            if not resp.ok:
                await ctx.send(f"Looks like something went wrong here. HTTP Code {resp.status}")
            soup = BeautifulSoup(str(await resp.text()), 'lxml')

        results = soup.find_all('ul', class_='mw-search-results')
        if not len(results):
            await ctx.send(NOTHING_FOUND)
            return
        links = results[0 if lang == "cpp" else 1].find_all('a', limit=8)
        lines = [f"[`{a.string}`](https://en.cppreference.com/{a.get('href')})" for a in links]
        await ctx.send(embed=format_embed(lines))
        self.cache[lang][text] = lines

    async def c(self, ctx, url, text):
        await self.c_or_cpp(ctx, url, text, lang="c")

    async def cpp(self, ctx, url, text):
        await self.c_or_cpp(ctx, url, text, lang="cpp")

    @staticmethod
    def parse_url(url):
        return quote_plus(url, safe=';/?:@&=$,><-[]')

    async def do_other(self, ctx, doc, url, query):
        if lines := self.cache.get(doc, {}).get(query):
            await ctx.send(embed=format_embed(lines))
        else:
            try:
                await getattr(self, doc)(ctx, url, query)
            except Exception as e:
                print(format_exception(type(e), e.__traceback__, e))
                return True


def format_embed(lines):
    e = discord.Embed(colour=discord.Colour.blurple())
    e.description = "\n".join(lines)
    return e


class RTFM(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._valid_docs = {
            "discord.py": Docs(
                url="https://discordpy.readthedocs.io/en/latest",
                aliases=("d.py", "dpy"),
                lang="Python"
            ),
            "python": Docs(
                url="https://docs.python.org/3",
                aliases=("py",),
                lang="Python",
                _type="Language"
            ),
            "zaneapi": Docs(
                url="https://docs.zaneapi.com/en/latest",
                aliases=("zane",),
                lang="N/A",
                _type="API"
            ),
            "pillow": Docs(
                url="https://pillow.readthedocs.io/en/stable",
                aliases=("pil",),
                lang="Python"
            ),
            "asyncpg": Docs(
                url="https://magicstack.github.io/asyncpg/current",
                lang="Python"
            ),
            "aiohttp": Docs(
                url="https://docs.aiohttp.org/en/stable",
                lang="Python"
            ),
            "wand": Docs(
                url="https://docs.wand-py.org/en/0.6.5",
                lang="Python"
            ),
            "numpy": Docs(
                url="https://numpy.org/doc/1.20",
                aliases=('np',),
                lang="Python"
            ),
            "rust": Docs(
                url="https://doc.rust-lang.org/std/?search=",  # url="https://doc.rust-lang.org/std/all.html",
                doc_url="https://doc.rust-lang.org/std/all.html",
                method=1,
                aliases=('rs',),
                lang="Rust",
                _type="Language"
            ),
            "beautifulsoup": Docs(
                url="https://www.crummy.com/software/BeautifulSoup/bs4/doc",
                aliases=('bs4', 'beautifulsoup4'),
                lang="Python"
            ),
            "flask": Docs(
                url="https://flask.palletsprojects.com/en/1.1.x",
                lang="Python"
            ),
            "pymongo": Docs(
                url="https://pymongo.readthedocs.io/en/stable",
                lang="Python"
            ),
            "yarl": Docs(
                url="https://yarl.readthedocs.io/en/latest",
                lang="Python"
            ),
            "requests": Docs(
                url="https://docs.python-requests.org/en/master",
                lang="Python"
            ),
            "selenium-py": Docs(
                url="https://www.selenium.dev/selenium/docs/api/py",
                lang="Python",
                aliases=('selenium-python',)
            ),
            "pandas": Docs(
                url="https://pandas.pydata.org/pandas-docs/stable",
                lang="Python"
            ),
            "pygame": Docs(
                url="https://www.pygame.org/docs",
                lang="Python"
            ),
            "matplotlib": Docs(
                url="https://matplotlib.org/stable",
                lang="Python"
            ),
            "c": Docs(
                url="https://cppreference.com/w/c/index.php",
                lang="C",
                _type="Language",
                method=1
            ),
            "cpp": Docs(
                url="https://cppreference.com/w/cpp/index.php",
                lang="C++",
                _type="Language",
                aliases=('c++',),
                method=1
            ),
            "sqlalchemy": Docs(
                url="https://docs.sqlalchemy.org/en/14",
                lang="Python"
            ),
            "discordjs": Docs(
                url="https://djsdocs.sorta.moe/v2/embed?src=stable&q=",
                doc_url="https://discord.js.org/#/docs/main/stable/general/welcome",
                method=1,
                lang="JavaScript",
                aliases=("d.js", "djs", "discord.js")
            )
        }
        self.rtfm_cache = {item: {} for item in self._valid_docs}
        self.webscrape = WebScrapeRTFM(self.bot, [m for m, value in self._valid_docs.items() if value.method == 1])

    def get_url(self, key, parsing=True):
        doc = self._valid_docs[key]
        if parsing:
            return doc.url
        else:
            if doc_url := doc.doc_url:
                return doc_url
            return doc.url

    async def build_table(self, key):
        url = self.get_url(key)
        async with self.bot.session.get(url + '/objects.inv') as resp:
            if resp.status != 200:
                raise RuntimeError('Cannot build rtfm lookup table, try again later.')

            stream = SphinxObjectFileReader(await resp.read())
            self.rtfm_cache[key] = parse_object_inv(stream, url)

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
            await ctx.send(self.get_url(key, False))
            return

        method = self._valid_docs[key].method
        if method == 0:
            await self.from_sphinx(ctx, key, obj)
        if method == 1:
            not_worked = await self.webscrape.do_other(ctx, key, self.get_url(key), obj)
            if not_worked:
                await ctx.send("Looks like something went wrong.")

    def get_key(self, query):
        for key, value in self._valid_docs.items():
            if key == query:
                return key
            if aliases := value.aliases:
                if query in aliases:
                    return key

    @property
    def valid_docs(self):
        items = {name: name for name in self._valid_docs}
        for name, doc in self._valid_docs.items():
            if not doc.aliases:
                continue
            for alias in doc.aliases:
                items[alias] = name
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
        embed.description = "Note that some may share the same results.\n`" + "`, `".join(sorted(self.valid_docs)) + "`"
        await ctx.send(embed=embed)

    @rtfm.command()
    async def info(self, ctx, documentation):
        if documentation not in self.valid_docs:
            await self.valid(ctx)
            return
        proper_doc = self.valid_docs[documentation]
        info = self._valid_docs[proper_doc]
        embed = discord.Embed(title=f"Documentation Info for {proper_doc}", color=discord.Color.blurple())
        desc = [
            f"Language: {info.lang}",
            f"Type: {info.type}",
            f"URL: {self.get_url(proper_doc, False)}"
        ]
        if aliases := info.aliases:
            desc.append("Aliases: `" + "`, `".join(aliases) + "`")
        embed.description = "\n".join(desc)
        await ctx.send(embed=embed)
