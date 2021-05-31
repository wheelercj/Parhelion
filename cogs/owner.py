# External imports
from replit import db
import discord
from discord.ext import commands
import textwrap
import asyncio
from discord.ext.commands.cooldowns import BucketType

# Internal imports
from common import remove_backticks

class Owner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.command(hidden=True)
    @commands.is_owner()
    @commands.cooldown(1, 15, BucketType.user)
    async def leave(self, ctx):
        '''Makes the bot leave the server'''
        await ctx.send(f'Now leaving the server. Goodbye!')
        await ctx.guild.leave()


    @commands.command(name='r', hidden=True)
    @commands.is_owner()
    @commands.cooldown(1, 15, BucketType.user)
    async def repeat_command(self, ctx, n : int = 1, skip: int = 0):
        '''Repeats the last command you used'''
        previous = ctx.bot.previous_command_ctxs
        if not len(previous):
            await ctx.send('No previous commands saved.')
        else:
            for i in range(n + skip, skip, -1):
                try:
                    c = previous[-i]
                    if c.author.id != ctx.author.id:
                        raise ValueError
                    else:
                        await c.reinvoke()
                        await asyncio.sleep(n * 2.5)
                except IndexError:
                    pass


    @commands.command(name='reload', hidden=True)
    @commands.is_owner()
    @commands.cooldown(1, 15, BucketType.user)
    async def reload_extension(self, ctx, *, extension: str):
        '''Reloads an extension, e.g: ;reload cogs.music'''
        try:
            self.bot.unload_extension(extension)
            self.bot.load_extension(extension)
        except Exception as e:
            await ctx.send(f'Error: {type(e).__name__}: {e}')
        else:
            await ctx.send('Extension successfully reloaded.')


    @reload_extension.error
    async def reload_extension_error(self, ctx, error):
        message = ''
        if isinstance(error, commands.errors.MissingRequiredArgument):
            message += str(error) + '\nExtensions: '
            message += ', '.join(self.bot.extensions.keys())

            await ctx.send(message)
        else:
            await ctx.send(error)


    @commands.command(name='load', hidden=True)
    @commands.is_owner()
    @commands.cooldown(1, 15, BucketType.user)
    async def load_extension(self, ctx, *, extension: str):
        '''Loads an extension, e.g. ;load cogs.music'''
        try:
            self.bot.load_extension(extension)
        except Exception as e:
            await ctx.send(f'Error: {type(e).__name__}: {e}')
        else:
            await ctx.send('Extension successfully loaded.')


    @commands.command(name='unload', hidden=True)
    @commands.is_owner()
    @commands.cooldown(1, 15, BucketType.user)
    async def unload_extension(self, ctx, *, extension: str):
        '''Unloads an extension, e.g. ;unload cogs.music'''
        try:
            self.bot.unload_extension(extension)
        except Exception as e:
            await ctx.send(f'Error: {type(e).__name__}: {e}')
        else:
            await ctx.send('Extension successfully unloaded.')


    @commands.command(name='reloadall', hidden=True)
    @commands.is_owner()
    @commands.cooldown(1, 15, BucketType.user)
    async def reload_all_extensions(self, ctx):
        '''Reloads all currently loaded extensions'''
        message = ''
        extensions = list(self.bot.extensions.keys())
        for extension in extensions.copy():
            try:
                self.bot.unload_extension(extension)
                self.bot.load_extension(extension)
            except Exception as e:
                message += f'\nError: {type(e).__name__}: {e}'
            else:
                message += f'\nExtension {extension} successfully reloaded.'
            
        await ctx.send(message)


    @commands.command(name='eval', hidden=True)
    @commands.is_owner()
    @commands.cooldown(1, 15, BucketType.user)
    async def _eval(self, ctx, *, expression: str):
        '''Evaluates a Python expression
        
        Returns result to Discord automatically.
        Has access to bot via self.
        '''
        # This command must never be made available to anyone besides
        # this bot's developers.
        try:
            await ctx.send(eval(expression))
        except Exception as e:
            await ctx.send(f'Python error: {e}')


    @commands.command(name='exec', hidden=True)
    @commands.is_owner()
    @commands.cooldown(1, 15, BucketType.user)
    async def _exec(self, ctx, *, statement: str):
        '''Executes a Python statement
        
        Requires the use of `await ctx.send` for output.
        Has direct access to bot.
        '''
        # This command must never be made available to anyone besides
        # this bot's developers.
        statement = remove_backticks(statement)
        env = {
            'ctx': ctx,
            'bot': self.bot,
            'asyncio': asyncio,
        }

        try:
            code = f'async def func():\n    try:\n{textwrap.indent(statement, "        ")}\n    except Exception as e:\n        await ctx.send("Python error: %s" % e)\nasyncio.get_running_loop().create_task(func())'
            exec(code, env)
        except Exception as e:
            await ctx.send(f'Python error: {e}')


    @commands.command(name='shut-down', aliases=['close', 'quit', 'exit'], hidden=True)
    @commands.is_owner()
    async def _close(self, ctx):
        '''Shuts down the bot'''
        await self.bot.close()


    @commands.command(name='dev-about', hidden=True)
    @commands.is_owner()
    async def dev_about(self, ctx):
        '''Shows development info about the bot'''
        embed = discord.Embed(title='Parhelion#3922')
        
        embed.add_field(name='total reminders\u2800', value=str(len(db)))
        
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Owner(bot))
