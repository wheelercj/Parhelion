# external imports
import discord
from discord.abc import Messageable
from discord.ext import commands
from datetime import datetime, timedelta, timezone
import asyncio
import asyncpg
from aiohttp.client_exceptions import ContentTypeError
import json
from typing import Union, Tuple

# internal imports
from cogs.utils.io import safe_send
from cogs.utils.time import parse_time_message, create_short_timestamp


'''
    CREATE TABLE IF NOT EXISTS daily_quotes (
        author_id BIGINT PRIMARY KEY,
        start_time TIMESTAMPTZ NOT NULL,
        target_time TIMESTAMPTZ NOT NULL,
        is_dm BOOLEAN NOT NULL,
        server_id BIGINT,
        channel_id BIGINT
    )
'''


class RunningQuoteInfo:
    def __init__(self, target_time: datetime, author_id: int):
        self.target_time = target_time
        self.author_id = author_id


class Quotes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._task = self.bot.loop.create_task(self.run_daily_quotes())
        self.running_quote_info: RunningQuoteInfo = None


    def cog_unload(self):
        self._task.cancel()


    async def run_daily_quotes(self) -> None:
        """A task that finds the next quote time, waits for that time, and sends"""
        await self.bot.wait_until_ready()
        try:
            while not self.bot.is_closed():
                target_time, author_id, destination = await self.get_next_quote_info()
                if target_time is None:
                    self.running_quote_info = None
                    self._task.cancel()
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
            self._task.cancel()
            self._task = self.bot.loop.create_task(self.run_daily_quotes())


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
            self._task = self.bot.loop.create_task(self.run_daily_quotes())
        elif target_time < self.running_quote_info.target_time:
            self._task.cancel()
            self._task = self.bot.loop.create_task(self.run_daily_quotes())
        
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
                self._task.cancel()
                self._task = self.bot.loop.create_task(self.run_daily_quotes())
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
                self._task.cancel()
                self._task = self.bot.loop.create_task(self.run_daily_quotes())
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
    bot.add_cog(Quotes(bot))
