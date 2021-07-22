# external imports
import discord
from discord.ext import commands


'''
    CREATE TABLE IF NOT EXISTS command_access_settings (
        id SERIAL PRIMARY KEY,
        command_name TEXT,
        is_blacklist BOOL DEFAULT TRUE,  -- else it's a whitelist
        is_user_ids BOOL DEFAULT TRUE,   -- else it's a list of server IDs
        object_ids BIGINT[]
    )
'''
# Each command may have multiple rows.


class Settings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    async def cog_check(self, ctx):
        if not await self.bot.is_owner(ctx.author):
            raise commands.NotOwner
        return True


    @commands.group(aliases=['s'])
    async def setting(self, ctx, *, command_name: str):
        """Shows the settings for a command"""
        records = await self.bot.db.fetch('''
            SELECT *
            FROM command_access_settings
            WHERE command_name = $1;
            ''', command_name)

        if records is None or not len(records):
            await ctx.send(f'No settings found for {command_name}.')
            return

        content = ''
        for r in records:
            content += f'\n\nID: {r["id"]}\n'
            if r['is_blacklist']:
                content += 'blacklist of '
            else:
                content += 'whitelist of '
            if r['is_user_ids']:
                content += 'users:'
            else:
                content += 'servers:'
            for ID in r['object_ids']:
                content += f'\n {ID}'

        embed = discord.Embed()
        embed.add_field(name=f'{command_name} settings', value=content)
        await ctx.send(embed=embed)


    @setting.command(name='create', aliases=['c'])
    async def create_setting(self, ctx, *, command_name: str):
        """"""
        if command_name not in self.bot.commands:
            raise commands.BadArgument(f'Command "{command_name}" not found.')


def setup(bot):
    bot.add_cog(Settings(bot))
