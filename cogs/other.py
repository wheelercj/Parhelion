# External imports
import discord
from discord.ext import commands
import json

# Internal imports
from common import remove_backticks, send_traceback


class Other(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.command(aliases=['calc', 'solve', 'maths'])
    async def math(self, ctx, *, expression: str):
        """Evaluates a math expression
        
        Evaluates multiple expressions if they're on separate lines, and supports code blocks.
        Uses the math.js API: https://mathjs.org/docs/expressions/syntax.html
        """
        try:
            expression = remove_backticks(expression)
            if '**' in expression:
                raise ValueError('This command uses ^ rather than ** for exponents.')
            raw_expressions = expression.split('\n')
            expressions = json.dumps(raw_expressions)
            expressions_json = '{\n"expr": ' + expressions + '\n}'

            async with ctx.typing():
                async with self.bot.session.post('http://api.mathjs.org/v4/',
                    data = expressions_json,
                    headers = {'content-type': 'application/json'},
                    timeout = 10
                ) as response:
                    if not response and response.status != 400:
                        raise ValueError(f'API request failed with status code {response.status}.')

                    json_text = await response.json()

                    if response.status == 400:
                        raise ValueError(json_text['error'])

            result = ''
            for i, expr in enumerate(raw_expressions):
                result += '\n`' + expr + '` = `' + json_text['result'][i] + '`'

            embed = discord.Embed(description=result)
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(e)
            if await self.bot.is_owner(ctx.author):
                await send_traceback(ctx, e)


    @commands.command(aliases=['rotate', 'rot', 'shift'])
    async def cipher(self, ctx, n: int, *, message: str):
        """Rotates each letter n letters through the alphabet"""
        message = message.lower()
        new_string = ''
        alphabet = 'abcdefghijklmnopqrstuvwxyz'
        for char in message:
            index = alphabet.find(char)
            if index != -1:
                new_index = (index + n) % 26
                new_string += alphabet[new_index]
            else:
                new_string += char

        await ctx.send(new_string)


def setup(bot):
    bot.add_cog(Other(bot))
