from core import Bot

bot = Bot(command_prefix="$", max_messages=1)
if __name__ == "__main__":
    bot.run()
