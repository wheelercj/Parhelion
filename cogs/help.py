# external imports
import discord
from discord.ext import commands
from datetime import datetime
import platform

# internal imports
from common import dev_settings, get_prefixes_str


# Guide on subclassing HelpCommand: https://gist.github.com/InterStella0/b78488fb28cadf279dfd3164b9f0cf96
class Embedded_Minimal_Help_Command(commands.MinimalHelpCommand):
    def __init__(self):
        super().__init__()
        self.command_attrs = {
            'name': 'help',
            'aliases': ['helps', 'command', 'commands']
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


    @commands.command(aliases=['invite', 'support', 'owner', 'privacy-policy', 'privacy', 'prefixes'])
    async def about(self, ctx):
        """Shows general info about this bot"""
        embed = discord.Embed(title=f'{self.bot.user.name}#{self.bot.user.discriminator}')
        prefixes = await get_prefixes_str(self.bot, ctx.message)
        owner = self.bot.get_user(self.bot.owner_id)
        
        embed.add_field(name='prefixes\u2800',
            value=f'{prefixes}\u2800\n\u2800')
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


    @commands.command(aliases=['ping', 'uptime'])
    async def stats(self, ctx):
        """Shows statistics about this bot"""
        embed = discord.Embed()
        embed.add_field(name='stats',
            value=f'websocket latency: {self.bot.latency * 1000:.2f} ms\n' \
                f'uptime: {await self.uptime(ctx)}\n' \
                f'servers: {len(self.bot.guilds)}\n' \
                f'users: {len(self.bot.users)}\n' \
                f'commands: {len(self.bot.commands)}\n' \
                f'commands used since last restart: {self.bot.command_use_count}\n' \
                f'commands {ctx.author} can use here: {await self.count_available_cmds(ctx)}\n')

        await ctx.send(embed=embed)


    async def uptime(self, ctx) -> str:
        """Returns the amount of time the bot has been running"""
        _uptime = ctx.message.created_at - self.bot.launch_time
        hours, remainder = divmod(int(_uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)
        return f'{days}d, {hours}h, {minutes}m, {seconds}s'


    async def count_available_cmds(self, ctx) -> int:
        """Counts the commands that ctx.author can use"""
        count = 0
        for cmd in self.bot.commands:
            try:
                if await cmd.can_run(ctx):
                    count += 1
            except commands.CommandError:
                pass
        return count


def setup(bot):
    bot.add_cog(Help(bot))
