# External imports
from discord.ext import commands
import textwrap
import asyncio
from discord.ext.commands.cooldowns import BucketType

# Internal imports
from common import remove_backticks


class Owner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.command(name='shut-down')
    @commands.is_owner()
    async def shut_down(self, ctx):
        '''Shuts down the bot'''
        await self.bot.close()


    @commands.command()
    @commands.is_owner()
    @commands.cooldown(1, 15, BucketType.user)
    async def leave(self, ctx):
        '''Makes the bot leave the server'''
        await ctx.send(f'Now leaving the server. Goodbye!')
        await ctx.guild.leave()


    @commands.command(name='repeat', aliases=['r', 'reinvoke'])
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


    @commands.command(name='list-exts', aliases=['list-ext', 'list-extensions'])
    @commands.is_owner()
    @commands.cooldown(1, 15, BucketType.user)
    async def list_extensions(self, ctx):
        '''Lists all currently loaded extensions'''
        message = 'Currently loaded extensions:\n' \
            + '\n'.join(self.bot.extensions.keys())
        await ctx.send(message)


    @commands.command(name='reload', aliases=['reload-ext', 'reload-exts'])
    @commands.is_owner()
    @commands.cooldown(1, 15, BucketType.user)
    async def reload_extension(self, ctx, *, extension: str):
        '''Reloads an extension'''
        extensions = extension.split()
        message = ''
        for ext in extensions:
            try:
                self.bot.unload_extension(ext)
                self.bot.load_extension(ext)
                message += f'\nExtension {ext} successfully reloaded.'
            except Exception as e:
                message += f'\nError: {type(e).__name__}: {e}'

        await ctx.send(message)


    @reload_extension.error
    async def reload_extension_error(self, ctx, error):
        message = ''
        if isinstance(error, commands.errors.MissingRequiredArgument):
            message += str(error) + '\nExtensions: '
            message += ', '.join(self.bot.extensions.keys())

            await ctx.send(message)
        else:
            await ctx.send(error)


    @commands.command(name='load', aliases=['load-ext', 'load-exts'])
    @commands.is_owner()
    @commands.cooldown(1, 15, BucketType.user)
    async def load_extension(self, ctx, *, extension: str):
        '''Loads an extension'''
        extensions = extension.split()
        message = ''
        for ext in extensions:
            try:
                self.bot.load_extension(ext)
                message += f'\nExtension {ext} successfully loaded.'
            except Exception as e:
                message += f'\nError: {type(e).__name__}: {e}'

        await ctx.send(message)


    @commands.command(name='unload', aliases=['unload-ext', 'unload-exts'])
    @commands.is_owner()
    @commands.cooldown(1, 15, BucketType.user)
    async def unload_extension(self, ctx, *, extension: str):
        '''Unloads an extension'''
        extensions = extension.split()
        message = ''
        for ext in extensions:
            try:
                self.bot.unload_extension(ext)
                message += f'\nExtension {ext} successfully unloaded.'
            except Exception as e:
                message += f'\nError: {type(e).__name__}: {e}'

        await ctx.send(message)


    @commands.command(name='reload-all', aliases=['reload-all-exts'])
    @commands.is_owner()
    @commands.cooldown(1, 15, BucketType.user)
    async def reload_all_extensions(self, ctx):
        '''Reloads all currently loaded extensions'''
        message = ''
        extensions = list(self.bot.extensions.keys())
        for ext in extensions.copy():
            try:
                self.bot.unload_extension(ext)
                self.bot.load_extension(ext)
                message += f'\nExtension {ext} successfully reloaded.'
            except Exception as e:
                message += f'\nError: {type(e).__name__}: {e}'
            
        await ctx.send(message)


    @commands.command(name='eval', aliases=['evaluate'])
    @commands.is_owner()
    @commands.cooldown(1, 15, BucketType.user)
    async def _eval(self, ctx, *, expression: str):
        '''Evaluates a Python expression
        
        Returns result to Discord.
        Has access to bot via self.
        '''
        # This command must never be made available to anyone
        # besides this bot's developers because Python's eval
        # function is not safe.
        try:
            await ctx.send(eval(expression))
        except Exception as e:
            await ctx.send(f'Python error: {e}')


    @commands.command(name='py', aliases=['python', 'exec', 'exe', 'execute'])
    @commands.is_owner()
    @commands.cooldown(1, 15, BucketType.user)
    async def _exec(self, ctx, *, statement: str):
        '''Executes a Python statement
        
        Requires use of `await ctx.send` for output.
        Has direct access to bot.
        '''
        # This command must never be made available to anyone
        # besides this bot's developers because Python's exec
        # function is not safe.
        statement = remove_backticks(statement)
        env = {
            'ctx': ctx,
            'bot': self.bot,
            'asyncio': asyncio,
        }

        try:
            code = f'async def func():\n    try:\n{textwrap.indent(statement, "        ")}\n    except Exception as e:\n        await ctx.send("Python error: %s" % e)\nasyncio.get_running_loop().create_task(func())'
            
            exec(code, env)
            await ctx.message.add_reaction('✅')
        except Exception as e:
            await ctx.send(f'Python error: {e}')


def setup(bot):
    bot.add_cog(Owner(bot))
