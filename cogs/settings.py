# external imports
from discord.ext import commands

'''
    CREATE TABLE IF NOT EXISTS settings (
        
    )
'''


class Settings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    async def cog_check(self, ctx):
        if not await self.bot.is_owner(ctx.author):
            raise commands.NotOwner
        return True


    @commands.group(name='settings', aliases=['s'])
    async def show_settings(self, ctx):
        """Shows all settings"""
        await ctx.send('There are no settings yet.')


def setup(bot):
    bot.add_cog(Settings(bot))
