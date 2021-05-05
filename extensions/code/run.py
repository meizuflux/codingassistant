import re
from typing import Optional

from discord.ext import commands, tasks

from ..utils import codeblock


class ExecuteCode(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.languages = {}
        self.prep.start()

    @tasks.loop(hours=24)
    async def prep(self):
        async with self.bot.session.get("https://emkc.org/api/v1/piston/versions") as resp:
            runtimes = await resp.json()
        for runtime in runtimes:
            language = runtime['name']
            self.languages[language] = language
            for alias in runtime['aliases']:
                if alias != language:
                    self.languages[alias] = language

    @commands.command(aliases=('exec', 'compile', 'execute', 'eval', 'e'))
    @commands.max_concurrency(1, commands.BucketType.user)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def run(self, ctx, language, *, code: str):
        language = language.strip('`').lower()
        if language not in self.languages:
            await ctx.send(f"Unsupported Language: **{language}**")
            return
        language = self.languages[language]
        first_line = code.splitlines()[0]
        if re.fullmatch(r'( |[0-9A-z]*)\b', first_line):
            code = code[len(first_line) + 1:]

        data = {
            "language": language,
            "source": code.strip('`'),
            "log": 0
        }
        async with self.bot.session.post("https://emkc.org/api/v1/piston/execute", json=data) as resp:
            data = await resp.json()
            await ctx.send(data)
            if not resp.ok:
                msg = f"```yaml\nThe API seems to be having an issue.\nStatus: {resp.status}"
                if r_msg := data.get('message'):
                    msg += f"\nMessage: {r_msg}"
                await ctx.reply(msg + '```', mention_author=False)
                return

        if not (output := data['output']):
            return await ctx.reply("Your code ran without output.", mention_author=False)
        if len(output) > 1000:
            await ctx.reply(
                f"The output was over 1000 characters, so I uploaded it here -> {await ctx.mystbin(output)}",
                mention_author=False)
            return

        output = output.strip().replace('```', '`\u200b``')
        message = (
            f"I ran your code in {language.capitalize()} {data.get('version')}.\n\n"
            f"{output}"
        )
        await ctx.reply(codeblock(message, lang='yaml'), mention_author=False)
