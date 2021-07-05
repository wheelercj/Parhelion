# external imports
from discord.ext import commands

# internal imports
from common import get_display_prefixes

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    async def cog_check(self, ctx):
        if not ctx.author.guild_permissions.administrator:
            raise commands.MissingRole('administrator')
        return True


    @commands.command(name='delete', aliases=['clear', 'cleanup'])
    @commands.bot_has_guild_permissions(read_message_history=True, manage_messages=True)
    async def _delete(self, ctx, n: int, confirm: str = None):
        """Deletes the previous n messages, up to 100

        This cannot be undone or stopped once it begins.
        You cannot delete messages more than 14 days old.
        """
        if confirm != 'CONFIRM':
            p = await get_display_prefixes(self.bot, ctx.message)
            await ctx.send(f'Are you sure you want to bulk-delete the last {n} messages? This cannot be undone or stopped once it begins. Use `{p[0]}delete {n} CONFIRM` to confirm.')
            return

        if n > 100:
            await ctx.send('You can delete up to 100 messages at once.')
            return

        messages = await ctx.channel.history(limit=n+1).flatten()
        await ctx.channel.delete_messages(messages[1:])


def setup(bot):
    bot.add_cog(Admin(bot))
