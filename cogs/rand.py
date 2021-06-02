import discord
from discord.ext import commands
from discord.ext.commands.cooldowns import BucketType
import random
import requests
import json


class Random(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.command(aliases=['random'])
    @commands.cooldown(1, 15, BucketType.user)
    async def rand(self, ctx, low: int = 1, high: int = 6):
        '''Gives a random number (default bounds: 1 and 6)'''
        low = int(low)
        high = int(high)
        if  low <= high:
            await ctx.send(str(random.randint(low, high)))
        else:
            await ctx.send(str(random.randint(high, low)))


    @commands.command(name='flip-coin', aliases=['flip', 'coin-flip'])
    @commands.cooldown(1, 15, BucketType.user)
    async def flip_coin(self, ctx):
        '''Flips a coin'''
        n = random.randint(1, 2)
        if n == 1:
            await ctx.send('heads')
        else:
            await ctx.send('tails')


    @commands.command()
    @commands.cooldown(1, 15, BucketType.user)
    async def quote(self, ctx):
        '''Shows a random famous quote'''
        args = {
            'lang':'en',
            'method':'getQuote',
            'format':'json'
        }
        response = requests.get('http://api.forismatic.com/api/1.0/', args)
        json_text = json.loads(response.text)
        quote, author = json_text['quoteText'], json_text['quoteAuthor']
        embed = discord.Embed(description=f'"{quote}"\n — {author}')
        await ctx.send(embed=embed)


    @commands.command()
    @commands.cooldown(1, 15, BucketType.user)
    async def choose(self, ctx, choice_count: int, *choices: str):
        '''Chooses randomly between multiple choices'''
        choices_made = []
        for _ in range(0, choice_count):
            choices_made.append(random.choice(choices))
        await ctx.send(''.join(choices_made))


    @choose.error
    async def choose_error(self, ctx, error):
        if isinstance(error, commands.errors.BadArgument) \
        or isinstance(error, commands.errors.CommandInvokeError) \
        or isinstance(error, commands.errors.MissingRequiredArgument):
            await ctx.send(f'Error: the first argument must be the number of choices you want to be made. Following arguments must be the choices to choose from.')
        else:
            await ctx.send(error)


def setup(bot):
    bot.add_cog(Random(bot))
