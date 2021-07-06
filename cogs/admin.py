# external imports
from discord.ext import commands
import asyncio


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    async def cog_check(self, ctx):
        if not ctx.guild:
            raise commands.NoPrivateMessage
        if not ctx.author.guild_permissions.administrator:
            raise commands.MissingRole('administrator')
        return True


    @commands.command(name='bulk-delete')
    @commands.bot_has_guild_permissions(read_message_history=True, manage_messages=True)
    async def bulk_delete(self, ctx, n: int, confirm: str = None):
        """Deletes the previous n messages in the current channel

        This cannot be undone or stopped once it begins.
        You cannot delete messages more than 14 days old.
        If the bot has the `manage messages` permission, messages from anyone
        will be deleted. If more than 100 messages are being deleted at once, 
        there will be a short delay between the deletion of each hundred
        messages.
        """
        if confirm != 'CONFIRM':
            await ctx.send(f'Are you sure you want to bulk-delete the last {n} messages in this channel? This cannot be undone or stopped once it begins. Use `{ctx.prefix}{ctx.invoked_with} {n} CONFIRM` to confirm.')
            return

        # discord.Channel.delete_messages can delete up to 100
        # messages each time it is called. If there are more than
        # 100 messages to delete, it will need to be called
        # multiple times.
        hundreds = n // 100
        remainder = n % 100

        for _ in range(hundreds):
            messages = await ctx.channel.history(limit=101).flatten()
            await ctx.channel.delete_messages(messages[1:])
            await asyncio.sleep(n/250)
        
        messages = await ctx.channel.history(limit=remainder+1).flatten()
        await ctx.channel.delete_messages(messages[1:])


def setup(bot):
    bot.add_cog(Admin(bot))
