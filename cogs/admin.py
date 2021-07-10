# external imports
import discord
from discord.ext import commands


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    async def cog_check(self, ctx):
        if not ctx.guild:
            raise commands.NoPrivateMessage
        if not ctx.author.guild_permissions.administrator:
            raise commands.MissingRole('administrator')
        return True


    @commands.command(name='bulk-delete', aliases=['bulkdelete'])
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
    bot.add_cog(Admin(bot))