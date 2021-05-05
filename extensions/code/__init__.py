from .rtfm import RTFM
from .run import ExecuteCode


def setup(bot):
    bot.add_cog(RTFM(bot))
    bot.add_cog(ExecuteCode(bot))
