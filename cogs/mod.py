# external imports
import discord
from discord.ext import commands
from typing import List
from copy import copy

# internal imports
from common import dev_settings, get_prefixes_message, get_prefixes_str


'''
CREATE TABLE custom_prefixes (
    id SERIAL PRIMARY KEY,
    server_id BIGINT UNIQUE,
    prefixes TEXT[],
    removed_default_prefixes TEXT[]
)
'''


class Mod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    async def cog_check(self, ctx):
        if not ctx.guild:
            raise commands.NoPrivateMessage
        return True


    @commands.group(invoke_without_command=True)
    @commands.has_guild_permissions(manage_guild=True)
    async def prefix(self, ctx):
        """A group of commands for managing this bot's command prefixes for this server"""
        prefixes = await get_prefixes_message(self.bot, ctx.message)
        await ctx.send(f"My current {prefixes}. You can use the `prefix add` and `prefix delete` commands to manage my command prefixes for this server.")


    @prefix.command(name='add')
    @commands.has_guild_permissions(manage_guild=True)
    async def add_prefix(self, ctx, *, new_prefix: str):
        """Adds a command prefix to the bot for this server"""
        if new_prefix.startswith('"') \
                    and new_prefix.endswith('"'):
                new_prefix = new_prefix[1:-1]
        if new_prefix.startswith(' '):
            await ctx.send('Prefixes cannot begin with a space.')
            return
        if not new_prefix or new_prefix == '':
            await ctx.send('Prefixless command invocation is not supported in servers.')
            return
        if len(new_prefix) > 10:
            await ctx.send('The maximum length of each command prefix is 10 characters.')
            return

        try:
            custom_prefixes: List[str] = self.bot.custom_prefixes[ctx.guild.id]
        except KeyError:
            custom_prefixes = []

        if f'␝{new_prefix}' in custom_prefixes:
            custom_prefixes.remove(f'␝{new_prefix}')
        else:
            if len(custom_prefixes) >= 10:
                await ctx.send('The maximum number of custom command prefixes is 10.')
                return

            custom_prefixes.append(new_prefix)
            custom_prefixes = sorted(custom_prefixes)

        self.bot.custom_prefixes[ctx.guild.id] = custom_prefixes
        await self.bot.save_all_custom_prefixes()
        await ctx.send(f'Successfully added the command prefix `{new_prefix}`')


    @prefix.command(name='delete')
    @commands.has_guild_permissions(manage_guild=True)
    async def delete_prefix(self, ctx, *, old_prefix: str):
        """Deletes one of the bot's command prefixes for this server
        
        You cannot delete the bot mention prefix (`@Parhelion`). If the prefix contains any spaces, wrap it in double quotes.
        """
        default_prefixes: List[str] = copy(dev_settings.default_bot_prefixes)
        try:
            custom_prefixes: List[str] = self.bot.custom_prefixes[ctx.guild.id]
        except KeyError:
            custom_prefixes = []

        if old_prefix.startswith('"') \
                and old_prefix.endswith('"'):
            old_prefix = old_prefix[1:-1]

        if old_prefix in custom_prefixes \
                or old_prefix in default_prefixes:
            if old_prefix in custom_prefixes:
                custom_prefixes.remove(old_prefix)
            else:
                custom_prefixes.append(f'␝{old_prefix}')

            self.bot.custom_prefixes[ctx.guild.id] = custom_prefixes
            await self.bot.save_all_custom_prefixes()
            await ctx.send(f'Successfully deleted command prefix `{old_prefix}`')
        else:
            await ctx.send('Prefix not found.')


    @prefix.command(name='reset')
    @commands.has_guild_permissions(manage_guild=True)
    async def reset_prefixes(self, ctx):
        """Resets the bot's command prefixes for this server to the defaults"""
        try:
            del self.bot.custom_prefixes[ctx.guild.id]
        except KeyError:
            await ctx.send('The prefixes are already set to the defaults.')
            return

        await self.bot.save_all_custom_prefixes()
        default_prefixes = await get_prefixes_str(self.bot, ctx.message)
        await ctx.send(f'Successfully reset the command prefixes to the defaults: {default_prefixes}')


    @commands.command(name='clean-up', aliases=['cleanup'])
    @commands.has_guild_permissions(manage_messages=True)
    @commands.bot_has_guild_permissions(read_message_history=True)
    async def clean_up(self, ctx, amount: int):
        """Deletes some of this bot's previous messages in the current channel

        The amount argument specifies how many messages to 
        search through, not necessarily how many to delete.
        This cannot be undone or stopped once it begins. You may 
        not be able to delete messages more than 14 days old.
        """
        check = lambda message: message.author == self.bot.user
        deleted = await ctx.channel.purge(limit=amount, check=check, bulk=False)
        await ctx.send(f':thumbsup: Deleted {len(deleted)} messages.', delete_after=8)


    @commands.command(name='bulk-delete', aliases=['bulkdelete'])
    @commands.has_guild_permissions(manage_guild=True)
    @commands.bot_has_guild_permissions(read_message_history=True, manage_messages=True)
    async def bulk_delete(self, ctx, amount: int, member: discord.Member = None):
        """Deletes some of the previous messages in the current channel

        If a user is specified, only their messages will be 
        deleted. The amount argument specifies how many messages 
        to search through, not necessarily how many to delete. 
        This cannot be undone or stopped once it begins. You may 
        not be able to delete messages more than 14 days old.
        """
        if member is None:
            check = None
        else:
            check = lambda message: message.author == member

        deleted = await ctx.channel.purge(limit=amount, check=check)
        await ctx.send(f':thumbsup: Deleted {len(deleted)} messages.', delete_after=8)


def setup(bot):
    bot.add_cog(Mod(bot))
