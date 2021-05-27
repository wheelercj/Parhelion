from discord.ext import commands
import textwrap
import asyncio
from discord.ext.commands.cooldowns import BucketType


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


    @commands.command(name='eval', hidden=True)
    @commands.is_owner()
    @commands.cooldown(1, 15, BucketType.user)
    async def _eval(self, ctx, *, expression: str):
        '''Evaluates a Python expression
        
        Returns result to Discord automatically.
        Has access to bot via self.
        '''
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
        statement = self.remove_backticks(statement)
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


    def remove_backticks(self, statement: str):
        '''Removes backticks around a code block, if they are there'''
        if statement.startswith('```'):
            statement = statement[3:]
            if statement.startswith('py\n'):
                statement = statement[3:]
            if statement.endswith('```'):
                statement = statement[:-3]

        return statement


def setup(bot):
    bot.add_cog(Owner(bot))
