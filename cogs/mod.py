# external imports
import discord
from discord.ext import commands


class Mod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


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
