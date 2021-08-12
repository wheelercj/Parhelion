# external imports
from cogs.utils.paginator import paginate_search
import discord
from discord.ext import commands
import json
import mystbin
import async_tio
from textwrap import dedent
import random

# internal imports
from cogs.utils.io import unwrap_code_block, send_traceback, get_attachment_url


class Other(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.command(aliases=['link', 'url', 'publish', 'post', 'paste', 'mystbin'])
    async def share(self, ctx, *, text: str = None):
        """Gives you a URL to your text or attachment

        Text is posted publicly on Mystb.in and cannot be edited or deleted once posted. Attachments stay on Discord's servers until deleted. For text, you can use a code block. Not all file types work for attachments.
        """
        async with ctx.typing():
            file_url = await get_attachment_url(ctx)
            if file_url:
                await ctx.send(f"Here's a link to the attachment: <{file_url}>")

            if text:
                syntax, text = await unwrap_code_block(text)
                text = dedent(text)
                mystbin_client = mystbin.Client(session=self.bot.session)
                paste = await mystbin_client.post(text, syntax=syntax)

                await ctx.reply(f'New Mystb.in paste created at <{paste.url}>')


    @commands.group(name='exec', invoke_without_command=True)
    async def _exec(self, ctx, *, code_block: str):
        """Executes code; use `exec list` to see supported languages
        
        When using the `exec languages` command, you can optionally choose a search word, e.g. `exec languages py` will only show languages that contain `py`.
        """
        # https://pypi.org/project/async-tio/
        async with ctx.typing():
            language, expression = await unwrap_code_block(code_block)
            async with await async_tio.Tio(loop=self.bot.loop, session=self.bot.session) as tio:
                if language not in tio.languages:
                    await ctx.send(f'Invalid language: {language}')
                    return

                result = await tio.execute(expression, language=language)
                await ctx.send(f'`{language}` output:\n' + str(result))


    @_exec.command(name='languages', aliases=['l', 'langs', 'list', 'search'])
    async def list_languages(self, ctx, *, query: str = None):
        """Lists the languages supported by the `exec` command that contain a search word
        
        You can also see a full list of supported languages here: https://tio.run/#
        """
        if query is None:
            title = 'languages supported by the `exec` command'
        else:
            title = f'supported languages that contain `{query}`'
        async with await async_tio.Tio(loop=self.bot.loop, session=self.bot.session) as tio:
            await paginate_search(ctx, title, tio.languages, query)


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


    @commands.command(name='random', aliases=['rand'], hidden=True)
    async def rand(self, ctx, low: int = 1, high: int = 6):
        """Gives a random number (default bounds: 1 and 6)"""
        low = int(low)
        high = int(high)
        if  low <= high:
            await ctx.send(str(random.randint(low, high)))
        else:
            await ctx.send(str(random.randint(high, low)))


    @commands.command(name='flip-coin', aliases=['flip', 'flipcoin'], hidden=True)
    async def flip_coin(self, ctx):
        """Flips a coin"""
        n = random.randint(1, 2)
        if n == 1:
            await ctx.send('heads')
        else:
            await ctx.send('tails')


    @commands.command(hidden=True)
    async def choose(self, ctx, choice_count: int, *choices: str):
        """Chooses randomly from multiple choices"""
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


    @commands.command(aliases=['rotate', 'rot', 'shift'], hidden=True)
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
