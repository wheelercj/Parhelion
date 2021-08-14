# external imports
import discord
from discord.ext import commands
import asyncpg
from typing import List

# internal imports
from cogs.utils.common import dev_settings, get_prefixes_message, get_prefixes_str


'''
CREATE TABLE prefixes (
    id SERIAL PRIMARY KEY,
    server_id BIGINT UNIQUE,
    custom_prefixes TEXT[],
    removed_default_prefixes TEXT[]
);
'''


class Mod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._task = bot.loop.create_task(self.load_custom_prefixes())


    async def cog_check(self, ctx):
        if not ctx.guild:
            raise commands.NoPrivateMessage
        return True


    async def load_custom_prefixes(self):
        await self.bot.wait_until_ready()
        try:
            records = await self.bot.db.fetch('''
                SELECT *
                FROM prefixes;
                ''')
            for r in records:
                self.bot.custom_prefixes[r['server_id']] = r['custom_prefixes']
                self.bot.removed_default_prefixes[r['server_id']] = r['removed_default_prefixes']
        except (OSError, discord.ConnectionClosed, asyncpg.PostgresConnectionError) as error:
            print(f'{error = }')
            self._task.cancel()
            self._task = self.bot.loop.create_task(self.load_custom_prefixes())


    @commands.group(invoke_without_command=True)
    @commands.has_guild_permissions(manage_guild=True)
    async def prefix(self, ctx):
        """A group of commands for managing this bot's command prefixes for this server"""
        prefixes = await get_prefixes_message(self.bot, ctx.message)
        await ctx.send(f'My current {prefixes}. You can use the `prefix add` and `prefix delete` commands to manage my command prefixes for this server.')


    @prefix.command(name='list', aliases=['l'])
    async def list_prefixes(self, ctx):
        """An alias for `prefix`; lists the current prefixes"""
        prefixes = await get_prefixes_message(self.bot, ctx.message)
        await ctx.send(f'My current {prefixes}. If you have the "manage server" permission, you can use the `prefix add` and `prefix delete` commands to manage my command prefixes for this server.')


    @prefix.command(name='add', aliases=['a'])
    @commands.has_guild_permissions(manage_guild=True)
    async def add_prefix(self, ctx, *, new_prefix: str):
        """Adds a command prefix to the bot for this server
        
        If the prefix contains any spaces, surround it with double quotes.
        """
        new_prefix = await self.strip_quotes(new_prefix)
        if new_prefix.startswith(' '):
            raise commands.BadArgument('Prefixes cannot begin with a space.')
        if not new_prefix or new_prefix == '':
            raise commands.BadArgument('Prefixless command invocation is not supported in servers.')
        if len(new_prefix) > 15:
            raise commands.BadArgument('The maximum length of each command prefix is 15 characters.')

        # Remove the new prefix from the removed default prefixes, if it is there.
        try:
            self.bot.removed_default_prefixes[ctx.guild.id].remove(new_prefix)
            await self.bot.db.execute('''
                UPDATE prefixes
                SET removed_default_prefixes = $1
                WHERE server_id = $2;
                ''', self.bot.removed_default_prefixes[ctx.guild.id], ctx.guild.id)
            await ctx.send(f'Successfully added the command prefix `{new_prefix}`')
            return
        except (KeyError, ValueError, AttributeError):
            pass

        try:
            custom_prefixes: List[str] = self.bot.custom_prefixes[ctx.guild.id]
            if custom_prefixes is None:
                custom_prefixes = []
        except KeyError:
            custom_prefixes = []
        if new_prefix in custom_prefixes:
            raise commands.BadArgument(f'The `{new_prefix}` command prefix already exists.')
        if len(custom_prefixes) >= 10:
            raise commands.UserInputError('The maximum number of custom command prefixes per server is 10.')

        custom_prefixes.append(new_prefix)
        self.bot.custom_prefixes[ctx.guild.id] = custom_prefixes
        await self.bot.db.execute('''
            INSERT INTO prefixes
            (server_id, custom_prefixes)
            VALUES ($1, $2)
            ON CONFLICT (server_id)
            DO UPDATE
            SET custom_prefixes = $2
            WHERE prefixes.server_id = $1;
            ''', ctx.guild.id, custom_prefixes)

        await ctx.send(f'Successfully added the command prefix `{new_prefix}`')


    @prefix.command(name='delete', aliases=['del'])
    @commands.has_guild_permissions(manage_guild=True)
    async def delete_prefix(self, ctx, *, old_prefix: str):
        """Deletes one of the bot's command prefixes for this server
        
        You cannot delete the bot mention prefix (`@Parhelion`). If the prefix contains any spaces, surround it with double quotes.
        """
        default_prefixes: List[str] = dev_settings.default_bot_prefixes
        try:
            custom_prefixes: List[str] = self.bot.custom_prefixes[ctx.guild.id]
            if custom_prefixes is None:
                custom_prefixes = []
        except KeyError:
            custom_prefixes = []

        new_prefix = await self.strip_quotes(old_prefix)

        if old_prefix in custom_prefixes:
            custom_prefixes.remove(old_prefix)
            self.bot.custom_prefixes[ctx.guild.id] = custom_prefixes
            await self.bot.db.execute('''
                UPDATE prefixes
                SET custom_prefixes = $1
                WHERE server_id = $2;
                ''', custom_prefixes, ctx.guild.id)
            await ctx.send(f'Successfully deleted the command prefix `{old_prefix}`')
            return

        elif old_prefix in default_prefixes:
            # Save the old prefix to the list of removed default prefixes.
            try:
                removed_default_prefixes = self.bot.removed_default_prefixes[ctx.guild.id]
                if removed_default_prefixes is None:
                    removed_default_prefixes = []
            except KeyError:
                removed_default_prefixes = []
            if old_prefix in removed_default_prefixes:
                raise commands.BadArgument(f'The `{old_prefix}` command prefix has already been deleted.')
            removed_default_prefixes.append(old_prefix)
            self.bot.removed_default_prefixes[ctx.guild.id] = removed_default_prefixes
            await self.bot.db.execute('''
                INSERT INTO prefixes
                (server_id, removed_default_prefixes)
                VALUES ($1, $2)
                ON CONFLICT (server_id)
                DO UPDATE
                SET removed_default_prefixes = $2
                WHERE prefixes.server_id = $1;
                ''', ctx.guild.id, removed_default_prefixes)
            await ctx.send(f'Successfully deleted the command prefix `{old_prefix}`')
            return

        await ctx.send('Prefix not found.')


    @prefix.command(name='reset')
    @commands.has_guild_permissions(manage_guild=True)
    async def reset_prefixes(self, ctx):
        """Resets the bot's command prefixes for this server to the defaults"""
        try: del self.bot.custom_prefixes[ctx.guild.id]
        except KeyError: pass
        try: del self.bot.removed_default_prefixes[ctx.guild.id]
        except KeyError: pass

        await self.bot.db.execute('''
            DELETE FROM prefixes
            WHERE server_id = $1;
            ''', ctx.guild.id)

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


    async def strip_quotes(self, message: str) -> str:
        """Removes one pair of double quotes around a message

        Works with both types of commonly used double quotes.
        """
        if message[0] in ('"', '“'):
            message = message[1:]
            if message[-1] in ('"', '“'):
                message = message[:-1]
        return message


def setup(bot):
    bot.add_cog(Mod(bot))
