from discord.ext import commands


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    async def cog_check(self, ctx):
        if not ctx.author.guild_permissions.administrator:
            raise commands.MissingRole('administrator')
        return True


    @commands.command(aliases=['cleanup'])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def clear(self, ctx, n: int):
        """Deletes the previous n messages, up to 100
        
        You cannot delete messages more than 14 days old.
        """
        if n > 100:
            await ctx.send('You can delete up to 100 messages at once.')
            return

        messages = await ctx.channel.history(limit=n+1).flatten()
        await ctx.channel.delete_messages(messages[1:])


def setup(bot):
    bot.add_cog(Admin(bot))
