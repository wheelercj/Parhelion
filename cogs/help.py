import discord
from discord.ext import commands


# Guide on subclassing HelpCommand: https://gist.github.com/InterStella0/b78488fb28cadf279dfd3164b9f0cf96
class Embedded_Minimal_Help_Command(commands.MinimalHelpCommand):
    def __init__(self):
        super().__init__()
        self.command_attrs = {
            'name': 'help',
            'aliases': ['helps', 'command', 'commands'],
            'cooldown': commands.Cooldown(1, 15, commands.BucketType.user)
        }

    async def send_pages(self):
        destination = self.get_destination()
        for page in self.paginator.pages:
            embed = discord.Embed(description=page)
            await destination.send(embed=embed)


class Help(commands.Cog):
    def __init__(self, bot):
       self.bot = bot
       help_command = Embedded_Minimal_Help_Command()
       help_command.cog = self
       bot.help_command = help_command


def setup(bot):
    bot.add_cog(Help(bot))
