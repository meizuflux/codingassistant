from core import Bot, Context
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote_plus

import discord
from bs4 import BeautifulSoup
from discord.ext import commands
from discord.utils import escape_markdown
from requests_html import AsyncHTMLSession

from extensions.code.func import SphinxObjectFileReader, finder, parse_object_inv

NOTHING_FOUND = "Your query returned no results."


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

    async def discordjs(self, ctx: Context, url: str, query: str) -> None:
        async with ctx.bot.session.get(parse_url(url + query)) as resp:
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
            self.cache['discord.js'][query] = lines

    #  made by komodo
    async def rust(self, ctx: Context, url: str, query: str) -> None:
        url = parse_url(url + query)
        sess = AsyncHTMLSession()
        r = await sess.get(url)
        await r.html.arender() #  This renders the page, JavaScript and all
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

    async def c_or_cpp(self, ctx: Context, url: str, text: str, lang: str) -> None:
        async with ctx.bot.session.get(parse_url(url + "?title=Special:Search&search=" + text)) as resp:
            if not resp.ok:
                await ctx.send(f"Looks like something went wrong here. HTTP Code {resp.status}")
            soup = BeautifulSoup(str(await resp.text()), 'lxml')

        results = soup.find_all('ul', class_='mw-search-results')
        try:
            links = results[0 if lang == "c++" else 1].find_all('a', limit=8)
        except IndexError:
            await ctx.send(NOTHING_FOUND)
            return

        lines = [f"[`{a.string}`](https://en.cppreference.com/{a.get('href')})" for a in links]
        await ctx.send(embed=format_embed(lines))
        self.cache[lang][text] = lines

    async def do_other(self, ctx: Context, doc: str, url: str, query: str) -> bool:
        if lines := self.cache.get(doc, {}).get(query):
            await ctx.send(embed=format_embed(lines))
            return True
        else:
            if doc == "discord.js":
                await self.discordjs(ctx, url, query)
                return True
            if doc == "rust":
                await self.rust(ctx, url, query)
                return True
            if doc in ("c", "c++"):
                await self.c_or_cpp(ctx, url, query, doc)
                return True
            raise KeyError("Documentation not found.")


def parse_url(url: str) -> str:
    return quote_plus(url, safe=';/?:@&=$,><-[]')


def format_embed(lines: list) -> discord.Embed:
    e = discord.Embed(colour=discord.Colour.green())
    e.description = "\n".join(lines)
    return e


class RTFM(commands.Cog):
    """Commands for querying documentation from various sources."""
    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self._valid_docs = {
            "Discord.py": Docs(
                url="https://discordpy.readthedocs.io/en/latest",
                aliases=("d.py", "dpy"),
                lang="Python"
            ),
            "Python": Docs(
                url="https://docs.python.org/3",
                aliases=("py",),
                lang="Python",
                _type="Language"
            ),
            "ZaneAPI": Docs(
                url="https://docs.zaneapi.com/en/latest",
                aliases=("zane",),
                lang="N/A",
                _type="API"
            ),
            "Pillow": Docs(
                url="https://pillow.readthedocs.io/en/stable",
                aliases=("pil",),
                lang="Python"
            ),
            "asyncpg": Docs(
                url="https://magicstack.github.io/asyncpg/current",
                lang="Python"
            ),
            "Aiohttp": Docs(
                url="https://docs.aiohttp.org/en/stable",
                lang="Python"
            ),
            "Wand": Docs(
                url="https://docs.wand-py.org/en/0.6.5",
                lang="Python"
            ),
            "NumPy": Docs(
                url="https://numpy.org/doc/1.20",
                aliases=('np',),
                lang="Python"
            ),
            "Rust": Docs(
                url="https://doc.rust-lang.org/std/?search=",  # url="https://doc.rust-lang.org/std/all.html",
                doc_url="https://doc.rust-lang.org/std/all.html",
                method=1,
                aliases=('rs',),
                lang="Rust",
                _type="Language"
            ),
            "BeautifulSoup": Docs(
                url="https://www.crummy.com/software/BeautifulSoup/bs4/doc",
                aliases=('bs4', 'beautifulsoup4'),
                lang="Python"
            ),
            "Flask": Docs(
                url="https://flask.palletsprojects.com/en/1.1.x",
                lang="Python"
            ),
            "PyMongo": Docs(
                url="https://pymongo.readthedocs.io/en/stable",
                lang="Python"
            ),
            "Motor": Docs(
                url="https://motor.readthedocs.io/en/stable",
                lang="Python"
            ),
            "Yarl": Docs(
                url="https://yarl.readthedocs.io/en/latest",
                lang="Python"
            ),
            "Wavelink": Docs(
                url="https://wavelink.readthedocs.io/en/latest",
                lang="Python"
            ),
            "Requests": Docs(
                url="https://docs.python-requests.org/en/master",
                lang="Python"
            ),
            "SymPy": Docs(
                url="https://docs.sympy.org/latest",
                lang="Python"
            ),
            "SciPy": Docs(
                url="https://docs.scipy.org/doc/scipy/reference",
                lang="Python"
            ),
            "Selenium-py": Docs(
                url="https://www.selenium.dev/selenium/docs/api/py",
                lang="Python",
                aliases=('selenium-python',)
            ),
            "IPython": Docs(
                url="https://ipython.readthedocs.io/en/stable",
                lang="Python"
            ),
            "twitchio": Docs(
                url="https://twitchio.readthedocs.io/en/latest",
                lang="Python"
            ),
            "PRAW": Docs(
                url="https://praw.readthedocs.io/en/latest",
                lang="Python"
            ),
            "Pandas": Docs(
                url="https://pandas.pydata.org/pandas-docs/stable",
                lang="Python"
            ),
            "PyGame": Docs(
                url="https://www.pygame.org/docs",
                lang="Python"
            ),
            "MatPlotLib": Docs(
                url="https://matplotlib.org/stable",
                lang="Python"
            ),
            "C": Docs(
                url="https://cppreference.com/w/c",
                lang="C",
                _type="Language",
                method=1
            ),
            "C++": Docs(
                url="https://cppreference.com/w/cpp",
                lang="C++",
                _type="Language",
                aliases=('cpp',),
                method=1
            ),
            "SqlAlchemy": Docs(
                url="https://docs.sqlalchemy.org/en/14",
                lang="Python"
            ),
            "Discord.js": Docs(
                url="https://djsdocs.sorta.moe/v2/embed?src=stable&q=",
                doc_url="https://discord.js.org/#/docs/main/stable/general/welcome",
                method=1,
                lang="JavaScript",
                aliases=("d.js", "djs")
            )
        }
        self.rtfm_cache = {item: {} for item in self._valid_docs}
        self.webscrape = WebScrapeRTFM(self.bot,
                                       [m.lower() for m, value in self._valid_docs.items() if value.method == 1])

    def get_url(self, key: str, parsing: bool=True) -> str:
        doc = self._valid_docs[key]
        if parsing:
            return doc.url
        else:
            if doc_url := doc.doc_url:
                return doc_url
            return doc.url

    async def build_table(self, key: str) -> None:
        url = self.get_url(key)
        async with self.bot.session.get(url + '/objects.inv') as resp:
            if resp.status != 200:
                raise RuntimeError('Cannot build rtfm lookup table, try again later.')

            stream = SphinxObjectFileReader(await resp.read())
            self.rtfm_cache[key] = parse_object_inv(stream, url)

    async def from_sphinx(self, ctx: Context, key: str, obj: str):
        if not self.rtfm_cache[key]:
            await ctx.trigger_typing()
            await self.build_table(key)

        cache = list(self.rtfm_cache[key].items())
        matches = finder(obj, cache, key=lambda t: t[0])[:8]

        if len(matches) == 0:
            return await ctx.send(NOTHING_FOUND)
        await ctx.send(embed=format_embed([f'[`{key}`]({url})' for key, url in matches]))

    async def do_rtfm(self, ctx: Context, key: str, obj: str):
        if obj is None:
            await ctx.send(self.get_url(key, False))
            return

        method = self._valid_docs[key].method
        if method == 0:
            await self.from_sphinx(ctx, key, obj)
        if method == 1:
            worked = await self.webscrape.do_other(ctx, key.lower(), self.get_url(key), obj)
            if not worked:
                await ctx.send("Looks like something went wrong.")

    def get_key(self, query: str) -> str:
        return self.valid_docs[query]

    @property
    def valid_docs(self) -> dict:
        items = {name.lower(): name for name in self._valid_docs}
        for name, doc in self._valid_docs.items():
            if not doc.aliases:
                continue
            for alias in doc.aliases:
                items[alias.lower()] = name
        return items

    @commands.group(
        invoke_without_command=True,
        aliases=('doc', 'documentation', 'docs', 'rtfs', 'rtm'),
        usage="<documentation> <query>"
    )
    async def rtfm(self, ctx: Context, documentation: str=None, *, query: str=None) -> None:
        """Sends documentation based on an entity."""
        if documentation is None and query is None:
            await self.valid(ctx)
            return
        documentation = documentation.lower()
        if not query:
            await self.info(ctx, documentation)
            return
        if documentation not in self.valid_docs:
            await self.valid(ctx)
            return
        await self.do_rtfm(ctx, key=self.get_key(documentation), obj=query)

    @rtfm.command()
    async def valid(self, ctx: Context):
        embed = discord.Embed(color=discord.Color.red())
        embed.title = "These are the valid items you can query for documentation."
        embed.description = f"Some of these may have aliases, you can use the `{ctx.prefix}rtfm info <doc>` command.\n\n`" + "`, `".join(
            sorted(self._valid_docs)) + "`"
        embed.set_footer(text="These docs are case-insensitive.")
        await ctx.send(embed=embed)

    @rtfm.command()
    async def info(self, ctx: Context, documentation: str):
        documentation = documentation.lower()
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
