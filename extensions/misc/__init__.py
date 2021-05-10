from core import Bot
from discord.ext import commands


class BotInfo(commands.Cog):
    """Information regarding the bot."""
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    @commands.command()
    async def info(self, ctx):
        await ctx.send("Hi i am little bot and I am made by ppotatoo#9688 erm yea")


def setup(bot):
    bot.add_cog(BotInfo())
