# external imports
import discord
from discord.abc import Messageable
from discord.ext import commands
from datetime import datetime, timedelta, timezone
from typing import List, Tuple
import asyncio
import asyncpg
from aiohttp.client_exceptions import ContentTypeError
import async_tio
import mystbin
from textwrap import dedent
import json
import random
from wordhoard import Definitions, Synonyms, Antonyms, Hypernyms, Hyponyms, Homophones

# internal imports
from cogs.utils.io import unwrap_code_block, send_traceback, get_attachment_url, safe_send
from cogs.utils.time import parse_time_message, create_short_timestamp
from cogs.utils.paginator import paginate_search, Paginator


'''
    CREATE TABLE daily_quotes (
        author_id BIGINT PRIMARY KEY,
        start_time TIMESTAMPTZ NOT NULL,
        target_time TIMESTAMPTZ NOT NULL,
        is_dm BOOLEAN NOT NULL,
        server_id BIGINT,
        channel_id BIGINT
    );
'''


class RunningQuoteInfo:
    def __init__(self, target_time: datetime, author_id: int):
        self.target_time = target_time
        self.author_id = author_id


class Other(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.quotes_task = self.bot.loop.create_task(self.run_daily_quotes())
        self.running_quote_info: RunningQuoteInfo = None


    def cog_unload(self):
        self.quotes_task.cancel()


    async def run_daily_quotes(self) -> None:
        """A task that finds the next quote time, waits for that time, and sends"""
        await self.bot.wait_until_ready()
        try:
            while not self.bot.is_closed():
                target_time, author_id, destination = await self.get_next_quote_info()
                if target_time is None:
                    self.running_quote_info = None
                    self.quotes_task.cancel()
                    return
                self.running_quote_info = RunningQuoteInfo(target_time, author_id)

                await discord.utils.sleep_until(target_time)

                try:
                    await self.send_quote(destination)
                    await self.update_quote_target_time(target_time, author_id)
                except (ContentTypeError, json.decoder.JSONDecodeError) as error:
                    print(f'{error = }')
                    await asyncio.sleep(30)
        except (OSError, discord.ConnectionClosed, asyncpg.PostgresConnectionError) as error:
            print(f'  run_daily_quotes {error = }')
            self.quotes_task.cancel()
            self.quotes_task = self.bot.loop.create_task(self.run_daily_quotes())


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
                    raise commands.BadArgument(f'Invalid language: {language}')

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


    @commands.command(name='calc', aliases=['calculate', 'solve', 'math', 'maths'])
    @commands.cooldown(25, 216, commands.BucketType.default)
    async def calculate(self, ctx, *, expression: str):
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


#################
# word commands #
#################


    @commands.command(aliases=['def', 'definition', 'definitions'])
    async def define(self, ctx, word: str):
        """Lists definitions of a given word"""
        # https://github.com/johnbumgarner/wordhoard
        definition = Definitions(word)
        results = definition.find_definitions()
        title = f'definition of `{word}`'
        await self.send_word_results(ctx, results, title)


    @commands.command(aliases=['syno', 'synonym'])
    async def synonyms(self, ctx, word: str):
        """Lists words with the same or similar meaning to a given word"""
        synonym = Synonyms(word)
        results = synonym.find_synonyms()
        title = f'synonyms of `{word}`'
        await self.send_word_results(ctx, results, title)


    @commands.command(aliases=['anto', 'antonym'])
    async def antonyms(self, ctx, word: str):
        """Lists words with the opposite meaning as a given word"""
        antonym = Antonyms(word)
        results = antonym.find_antonyms()
        title = f'antonyms of `{word}`'
        await self.send_word_results(ctx, results, title)


    @commands.command(aliases=['hyper', 'hypernym'])
    async def hypernyms(self, ctx, word: str):
        """Lists words of more general meaning than a given word"""
        hypernym = Hypernyms(word)
        results = hypernym.find_hypernyms()
        title = f'hypernyms of `{word}`'
        await self.send_word_results(ctx, results, title)


    @commands.command(aliases=['hypo', 'hyponym'])
    async def hyponyms(self, ctx, word: str):
        """Lists words of more specific meaning than a given word"""
        hyponym = Hyponyms(word)
        results = hyponym.find_hyponyms()
        title = f'hyponyms of `{word}`'
        await self.send_word_results(ctx, results, title)


    @commands.command(aliases=['homo', 'homophone'])
    async def homophones(self, ctx, word: str):
        """Lists words that sound the same as a given word"""
        homophone = Homophones(word)
        results = homophone.find_homophones()
        if results and not isinstance(results, str):
            for i, result in enumerate(results):
                results[i] = result.split()[-1]
        title = f'homophones of `{word}`'
        await self.send_word_results(ctx, results, title)


    async def send_word_results(self, ctx, results: List[str], title: str) -> None:
        """Bullet-points and paginates a list of strings in ctx"""
        if not results or isinstance(results, str):
            raise commands.BadArgument('No results found.')
        for i, result in enumerate(results):
            results[i] = '• ' + result
        paginator = Paginator(title=title, embed=True, timeout=90, use_defaults=True, entries=results, length=15)
        await paginator.start(ctx)


    @commands.command(name='auto-incorrect', aliases=['ai', 'autoincorrect'])
    async def auto_incorrect(self, ctx, *, words: str):
        """Replaces as many words as possible with different words that sound the same"""
        results = []
        for word in words.split():
            homophone = Homophones(word)
            result_sentences = homophone.find_homophones()
            if not result_sentences or isinstance(result_sentences, str):
                results.append(word)
            else:
                results.append(result_sentences[0].split()[-1])
        
        await ctx.send(' '.join(results))


#######################
# quote command group #
#######################


    @commands.group(invoke_without_command=True)
    async def quote(self, ctx, *, _time: str = None):
        """Shows a random famous quote
        
        If a time is provided in HH:mm format, a quote will be sent each day at that time.
        You can cancel daily quotes with `quote stop`.
        If you have not chosen a timezone with the `timezone set` command, UTC will be assumed.
        """
        if _time is None:
            await self.send_quote(ctx)
            return

        if _time.count(':') != 1 or _time[-1] == ':':
            raise commands.BadArgument('Please enter a time in HH:mm format. You may use 24-hour time or either AM or PM.')
        dt, _ = await parse_time_message(ctx, _time)
        now = datetime.now(timezone.utc)
        target_time = datetime(now.year, now.month, now.day, int(dt.hour), int(dt.minute), tzinfo=timezone.utc)
        if target_time < now:
            target_time += timedelta(days=1)

        await self.save_daily_quote_to_db(ctx, now, target_time)

        if self.running_quote_info is None:
            self.quotes_task = self.bot.loop.create_task(self.run_daily_quotes())
        elif target_time < self.running_quote_info.target_time:
            self.quotes_task.cancel()
            self.quotes_task = self.bot.loop.create_task(self.run_daily_quotes())
        
        timestamp = await create_short_timestamp(target_time)
        await ctx.send(f'Time set! At {timestamp} each day, I will send you a random quote.')


    @quote.command(name='stop', aliases=['del', 'delete'])
    async def stop_daily_quote(self, ctx):
        """Stops your daily quotes"""
        try:
            await self.bot.db.execute('''
                DELETE FROM daily_quotes
                WHERE author_id = $1;
                ''', ctx.author.id)
            if self.running_quote_info is not None \
                    and ctx.author.id == self.running_quote_info.author_id:
                self.quotes_task.cancel()
                self.quotes_task = self.bot.loop.create_task(self.run_daily_quotes())
        except Exception as e:
            await safe_send(ctx, f'Error: {e}', protect_postgres_host=True)
        else:
            await ctx.send('Your daily quotes have been stopped.')


    @quote.command(name='mod-delete', aliases=['mdel', 'moddelete'])
    @commands.has_guild_permissions(manage_messages=True)
    async def mod_delete_daily_quote(self, ctx, *, member: discord.Member):
        """Stops the daily quotes of anyone on this server"""
        try:
            await self.bot.db.execute('''
                DELETE FROM daily_quotes
                WHERE author_id = $1
                    AND server_id = $2;
                ''', member.id, ctx.guild.id)
            if self.running_quote_info is not None \
                    and member.id == self.running_quote_info.author_id:
                self.quotes_task.cancel()
                self.quotes_task = self.bot.loop.create_task(self.run_daily_quotes())
        except Exception as e:
            await safe_send(ctx, f'Error: {e}', protect_postgres_host=True)
        else:
            await ctx.send(f"{member.display_name}'s daily quotes have been stopped.")


    @quote.command(name='list', aliases=['l'])
    @commands.guild_only()
    async def list_daily_quote(self, ctx):
        """Lists everyone that set up daily quotes in this channel"""
        try:
            records = await self.bot.db.fetch('''
                SELECT author_id
                FROM daily_quotes
                WHERE server_id = $1
                    AND channel_id = $2;
                ''', ctx.guild.id, ctx.channel.id)
        except Exception as e:
            await safe_send(ctx, f'Error: {e}', protect_postgres_host=True)
            return

        if records is None or not len(records):
            raise commands.UserInputError('There are no daily quotes set up in this channel.')

        message = "Here's everyone that set up a daily quote in this channel:"
        for r in records:
            member = ctx.guild.get_member(r['author_id'])
            if member:
                name = f'{member.name}#{member.discriminator}'
            else:
                name = r['author_id']
            message += '\n' + name

        await ctx.send(message)


    async def save_daily_quote_to_db(self, ctx, start_time: datetime, target_time: datetime) -> None:
        """Saves one daily quote to the database"""
        if ctx.guild:
            is_dm = False
            server_id = ctx.guild.id
            channel_id = ctx.channel.id
        else:
            is_dm = True
            server_id = 0
            channel_id = 0

        await self.bot.db.execute('''
            INSERT INTO daily_quotes
            (author_id, start_time, target_time, is_dm, server_id, channel_id)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (author_id)
            DO UPDATE
            SET target_time = $3
            WHERE daily_quotes.author_id = $1;
            ''', ctx.author.id, start_time, target_time, is_dm, server_id, channel_id)


    async def get_next_quote_info(self) -> Tuple[datetime, int, Messageable]:
        """Gets from the database the info for the nearest (in time) daily quote task

        Returns (target_time, author_id, destination).
        If there is no next daily quote, this function returns (None, None, None).
        """
        r = await self.bot.db.fetchrow('''
            SELECT *
            FROM daily_quotes
            ORDER BY target_time
            LIMIT 1;
            ''')
        if r is None:
            return None, None, None

        target_time = r['target_time']
        author_id = r['author_id']
        if r['is_dm']:
            destination = self.bot.get_user(r['author_id'])
        else:
            server = self.bot.get_guild(r['server_id'])
            destination = server.get_channel(r['channel_id'])

        return target_time, author_id, destination


    async def update_quote_target_time(self, old_target_time: datetime, author_id: int) -> None:
        """Changes a daily quote's target time in the database to one day later"""
        new_target_time = old_target_time + timedelta(days=1)
        await self.bot.db.execute('''
            UPDATE daily_quotes
            SET target_time = $1
            WHERE author_id = $2
            ''', new_target_time, author_id)


    async def send_quote(self, destination: Messageable) -> None:
        """Immediately sends a random quote to destination
        
        May raise ContentTypeError or json.decoder.JSONDecodeError.
        """
        quote, author = await self.get_quote()
        embed = discord.Embed(description=f'"{quote}"\n — {author}')
        await destination.send(embed=embed)


    async def get_quote(self) -> Tuple[str, str]:
        """Gets a quote and the quote's author from the forismatic API
        
        May raise ContentTypeError or json.decoder.JSONDecodeError.
        """
        params = {
            'lang': 'en',
            'method': 'getQuote',
            'format': 'json'
        }
        async with self.bot.session.get('http://api.forismatic.com/api/1.0/', params=params) as response:
            json_text = await response.json()
        quote = json_text['quoteText']
        author = json_text['quoteAuthor']
        
        return quote, author


def setup(bot):
    bot.add_cog(Other(bot))
