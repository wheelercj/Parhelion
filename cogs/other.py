# external imports
import discord
from discord.ext import commands
import json
import mystbin
from textwrap import dedent

# internal imports
from common import unwrap_code_block, send_traceback


class Other(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.command(aliases=['calc', 'solve', 'maths'])
    @commands.cooldown(25, 216, commands.BucketType.default)
    async def math(self, ctx, *, expression: str):
        """Evaluates a math expression
        
        Evaluates multiple expressions if they're on separate lines, and
        allows you to use a code block. Uses the math.js API:
        https://mathjs.org/docs/expressions/syntax.html
        """
        # The math.js API has a 10 second duration limit per evaluation and 
        # allows a maximum of 10,000 requests per day (or 25 requests per 216
        # seconds).
        try:
            _, expression = await unwrap_code_block(expression)
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
                    if not response.ok and response.status != 400:
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


    @commands.command(aliases=['mystbin'])
    async def paste(self, ctx, *, content: str):
        """Creates a new paste on Mystb.in and gives you the link
        
        You can use a code block and specify syntax. You cannot
        specify syntax without a triple-backtick code block. The
        default syntax is `txt`. The pastes are public and
        cannot be edited or deleted once they are posted.
        """
        async with ctx.typing():
            syntax, content = await unwrap_code_block(content)
            content = dedent(content)
            mystbin_client = mystbin.Client(session=self.bot.session)
            paste = await mystbin_client.post(content, syntax=syntax)

            await ctx.reply(f'New Mystb.in paste created at <{paste.url}>')


def setup(bot):
    bot.add_cog(Other(bot))
