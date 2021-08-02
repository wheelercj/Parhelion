# external imports
import discord
from discord.ext import commands
import platform

# internal imports
from common import dev_settings, get_prefixes_message, get_prefixes_list


# Guide on subclassing HelpCommand: https://gist.github.com/InterStella0/b78488fb28cadf279dfd3164b9f0cf96
class Embedded_Minimal_Help_Command(commands.MinimalHelpCommand):
    def __init__(self):
        super().__init__()
        self.command_attrs = {
            'name': 'help',
            'aliases': ['h', 'helps', 'command', 'commands']
        }

    async def send_pages(self):
        destination = self.get_destination()
        for page in self.paginator.pages:
            embed = discord.Embed(description=page)
            await destination.send(embed=embed)


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.old_help_command = bot.help_command
        bot.help_command = Embedded_Minimal_Help_Command()
        bot.help_command.cog = self


    def cog_unload(self):
        self.bot.help_command = self.old_help_command


    @commands.command(hidden=True)
    async def prefixes(self, ctx):
        """Lists the bot's current prefixes for this server"""
        prefixes = await get_prefixes_message(self.bot, ctx.message)
        await ctx.send(f'My current {prefixes}')


    @commands.command(aliases=['invite', 'support', 'owner', 'privacy-policy', 'privacy'])
    async def about(self, ctx):
        """Shows general info about this bot"""
        embed = discord.Embed(title=f'{self.bot.user.name}#{self.bot.user.discriminator}')
        owner = self.bot.get_user(self.bot.owner_id)
        prefixes = await get_prefixes_list(self.bot, ctx.message)

        embed.add_field(name='\u200b\u2800',
            value=f'Use `{prefixes[0]}help` for help\nwith commands.\u2800\n\u2800')
        embed.add_field(name='\u2800owner\u2800',
            value=f'\u2800{owner.name}#{owner.discriminator}\u2800\n\u2800')
        embed.add_field(name='\u200b',
            value='\u200b\n\u200b')

        embed.add_field(name='links\u2800',
            value=f'[bot invite]({dev_settings.bot_invite_link})\u2800\n' \
                f'[support server]({dev_settings.support_server_link})\u2800\n' \
                f'[privacy policy]({dev_settings.privacy_policy_link})\u2800\n')
        embed.add_field(name='\u2800made with\u2800',
            value=f'\u2800Python v{platform.python_version()}\u2800\n' \
                f'\u2800and [discord.py](https://discordpy.readthedocs.io/en/latest/) v{discord.__version__}\u2800\n')
        embed.add_field(name='\u200b',
            value='\u200b')

        await ctx.send(embed=embed)


    @commands.command(hidden=True)
    async def source(self, ctx):
        await ctx.send('I am closed source.')


def setup(bot):
    bot.add_cog(Help(bot))
