from discord.ext import commands


class BotInfo(commands.Cog):

    @commands.command()
    async def info(self, ctx):
        await ctx.send("Hi i am little bot and I am made by ppotatoo#9688 erm yea")


def setup(bot):
    bot.add_cog(BotInfo())
