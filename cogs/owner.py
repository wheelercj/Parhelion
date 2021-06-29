# External imports
from discord.ext import commands
import textwrap
import inspect
import asyncio

# Internal imports
from common import remove_backticks


class Owner(commands.Cog):
    """Commands that can only be used by the bot owner"""
    def __init__(self, bot):
        self.bot = bot


    async def cog_check(self, ctx):
        if not await self.bot.is_owner(ctx.author):
            raise commands.NotOwner
        return True


    @commands.command()
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def echo(self, ctx, *, message: str):
        """Repeats a message"""
        await ctx.send(message)


    @commands.command(name='shut-down')
    async def shut_down(self, ctx):
        """Shuts down the bot"""
        await self.bot.close()


    @commands.command()
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def leave(self, ctx, *, server_name: str = None):
        """Makes the bot leave a server
        
        If no server name is given, the bot will leave the current server.
        """
        if server_name is None:
            if ctx.guild is None:
                await ctx.send('This command can only be used without an argument in a server.')
            else:
                await ctx.send(f'Now leaving the server. Goodbye!')
                await ctx.guild.leave()
        else:
            for server in ctx.bot.guilds:
                if server_name == server.name:
                    await ctx.send(f'Now leaving server: {server.name}')
                    await server.leave()
                    return

            await ctx.send('Server not found.')


    @commands.command(name='repeat', aliases=['r', 'reinvoke'])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def repeat_command(self, ctx, n : int = 1, skip: int = 0):
        """Repeats the last command you used"""
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
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def list_extensions(self, ctx):
        """Lists all currently loaded extensions"""
        message = 'Currently loaded extensions:\n' \
            + '\n'.join(self.bot.extensions.keys())
        await ctx.send(message)


    @commands.command(name='reload', aliases=['reload-ext', 'reload-exts'])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def reload_extension(self, ctx, *, extension: str):
        """Reloads an extension"""
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
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def load_extension(self, ctx, *, extension: str):
        """Loads an extension"""
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
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def unload_extension(self, ctx, *, extension: str):
        """Unloads an extension"""
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
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def reload_all_extensions(self, ctx):
        """Reloads all currently loaded extensions"""
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
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def _eval(self, ctx, *, expression: str):
        """Evaluates a Python expression
        
        Returns result to Discord.
        Has access to bot via self.
        """
        # This command must never be made available to anyone
        # besides this bot's developers because Python's eval
        # function is not safe.
        try:
            await ctx.send(eval(expression))
        except Exception as e:
            await ctx.send(f'Python error: {e}')


    @commands.command(name='py', aliases=['python', 'exec', 'exe', 'execute'])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def _exec(self, ctx, *, statement: str):
        """Executes a Python statement
        
        Requires use of `await ctx.send` for output.
        Has direct access to bot.
        """
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
            await ctx.message.add_reaction('❗')
            await ctx.send(f'Python error: {e}')


    @commands.command(name='inspect', aliases=['source', 'src', 'getsource'])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def _inspect(self, ctx, *, command: str):
        """Shows the source code of a command"""
        try:
            cmds = {cmd.name: cmd for cmd in self.bot.commands}
            if command not in cmds.keys():
                raise ValueError(f'Command {command} not found.')
            source = str(inspect.getsource(cmds[command].callback))
            await ctx.send(f'```py\n{source}```')
        except ValueError as e:
            await ctx.send(e)
        except KeyError as e:
            await ctx.send(e)


def setup(bot):
    bot.add_cog(Owner(bot))
