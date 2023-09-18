import discord  # https://pypi.org/project/discord.py/
from discord.ext import commands  # https://pypi.org/project/discord.py/


class Mod(commands.Cog):
    """Moderate the server."""

    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="clean-up", aliases=["cleanup"])
    @commands.has_guild_permissions(manage_messages=True)
    @commands.bot_has_guild_permissions(read_message_history=True)
    async def clean_up(self, ctx, amount: int):
        """Deletes some of this bot's previous messages in the current channel

        This cannot be undone or stopped once it begins. You may not be able to delete
        messages more than 14 days old.

        Parameters
        ----------
        amount: int
            The number of messages in this channel to delete this bot's messages within.
        """
        deleted = await ctx.channel.purge(
            limit=amount,
            check=lambda message: message.author == self.bot.user,
            bulk=False,
        )
        await ctx.send(f":thumbsup: Deleted {len(deleted)} messages.", delete_after=8)

    @commands.hybrid_command(name="bulk-delete")
    @commands.has_guild_permissions(manage_guild=True)
    @commands.bot_has_guild_permissions(read_message_history=True, manage_messages=True)
    async def bulk_delete(self, ctx, amount: int, member: discord.Member | None = None):
        """Deletes some of the previous messages in the current channel

        This cannot be undone or stopped once it begins. You may not be able to delete
        messages more than 14 days old. If a member is chosen, only their messages will
        be deleted and only if they are within the last chosen amount of anyone's
        messages in the channel.

        Parameters
        ----------
        amount: int
            The maximum number of previous messages in the current channel to delete.
        member: discord.Member | None
            The member to delete messages of.
        """
        if member is None:
            deleted = await ctx.channel.purge(limit=amount)
        else:
            deleted = await ctx.channel.purge(
                limit=amount, check=lambda message: message.author == member
            )
        await ctx.send(f":thumbsup: Deleted {len(deleted)} messages.", delete_after=8)

    async def strip_quotes(self, message: str) -> str:
        """Removes one pair of double quotes around a message

        Works with both types of commonly used double quotes.
        """
        if message[0] in ('"', "“"):
            message = message[1:]
            if message[-1] in ('"', "“"):
                message = message[:-1]
        return message


async def setup(bot):
    await bot.add_cog(Mod(bot))
