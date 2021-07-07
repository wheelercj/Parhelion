# external imports
from discord.ext import commands


class Mod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    async def cog_check(self, ctx):
        if not ctx.guild:
            raise commands.NoPrivateMessage
        return True


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


def setup(bot):
    bot.add_cog(Mod(bot))
