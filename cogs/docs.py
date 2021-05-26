import discord
from discord.ext import commands
from discord.ext.commands.cooldowns import BucketType


class Docs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.docs = {
            'inspect': '''A Python module for getting info about live objects such as modules, classes, methods, functions, tracebacks, frame objects, and code objects. Some of its functions: getdoc, getcomments, getmodule, getsource.
            More details: https://docs.python.org/3/library/inspect.html''',

            'discord.py': '''Homepage: https://discordpy.readthedocs.io/en/latest/index.html
            Discord server: https://discord.gg/r3sSKJJ'''
        }


    @commands.command(aliases=['listdocs'], hidden=True)
    @commands.cooldown(1, 15, BucketType.user)
    async def docs(self, ctx):
        '''Shows the names of all docs'''
        doc_names = ''
        for doc_name in self.docs.keys():
            doc_names += f'\n{doc_name}'
        embed = discord.Embed(title='doc names', description=doc_names)
        await ctx.send(embed=embed)


    @commands.command(hidden=True)
    @commands.cooldown(1, 15, BucketType.user)
    async def doc(self, ctx, *, name: str):
        '''Shows info about a topic'''
        try:
            embed = discord.Embed(title=name, description=self.docs[name])
            await ctx.send(embed=embed)
        except KeyError:
            await ctx.send(f'Could not find `{name}`.')


def setup(bot):
    bot.add_cog(Docs(bot))
