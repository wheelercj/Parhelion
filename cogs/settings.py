# external imports
import discord
from discord.ext import commands
import asyncpg


'''
    CREATE TABLE IF NOT EXISTS command_access_settings (
        id SERIAL PRIMARY KEY,
        command_name TEXT,
        access TEXT CONSTRAINT valid_access CHECK (access = ANY('{"allow", "deny", "limit"}')),
        object_type TEXT CONSTRAINT valid_type CHECK (object_type = ANY('{"server", "channel", "user"}')),
        object_ids BIGINT[],
        UNIQUE (command_name, access, object_type)
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


    @commands.group(aliases=['set'], invoke_without_command=True)
    async def setting(self, ctx, *, command_name: str):
        """Shows the settings for a command"""
        records = await self.bot.db.fetch('''
            SELECT *
            FROM command_access_settings
            WHERE command_name = $1;
            ''', command_name)

        if records is None or not len(records):
            await ctx.send(f'No settings found for "{command_name}".')
            return

        content = ''
        for r in records:
            content += f'\n\nID: {r["id"]}\n' \
                + r['access'] + ' access to ' \
                + r['object_type'] + 's:'
            for ID in r['object_ids']:
                content += f'\n {ID}'

        embed = discord.Embed()
        embed.add_field(name=f'{command_name} settings', value=content)
        await ctx.send(embed=embed)


    @setting.command(name='server', aliases=['s'])
    async def server_cmd_access(self, ctx, server: discord.Guild, access: str, *, command_name: str):
        """Manages commands access for a server

        For the `access` argument, you may enter "allow", "deny", or "limit". The command name must not contain any aliases.
        """
        await self.save_cmd_setting('server', server.id, access, command_name)
        await ctx.message.add_reaction('✅')


    async def save_cmd_setting(self, object_type: str, object_id: int, access: str, command_name: str) -> None:
        """Validates and saves a new command access setting to the database"""
        # Validate the arguments.
        if object_type not in ('server', 'channel', 'user'):
            raise ValueError
        access = access.strip('"')
        if access not in ('allow', 'deny', 'limit'):
            raise commands.BadArgument('Please enter either "allow", "deny", or "limit" before the command that you are changing the settings of.')
        all_command_names = [x.name for x in self.bot.commands]
        entered = command_name.split(' ')
        for cmd_name in entered:
            if cmd_name not in all_command_names:
                raise commands.BadArgument(f'Command "{cmd_name}" not found.')

        try:
            # Create a new row for this setting, but only if one does not
            # already exist for this type of setting.
            await self.bot.db.execute("""
                INSERT INTO command_access_settings
                (command_name, access, object_type, object_ids)
                VALUES ($1, $2, $3, $4);
                """, command_name, access, object_type, [object_id])
        except asyncpg.exceptions.UniqueViolationError:
            # If a row for this type of setting already exists,
            # update the existing row.
            await self.bot.db.execute("""
                UPDATE command_access_settings
                SET object_ids = object_ids || $1
                WHERE command_name = $2
                    AND access = $3
                    AND object_type = $4
                    AND $1 != ANY(object_ids);
                """, object_id, command_name, access, object_type)


def setup(bot):
    bot.add_cog(Settings(bot))
