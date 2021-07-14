# external imports
import discord
from discord.ext import commands
from datetime import datetime, timedelta
import asyncio
from aiohttp.client_exceptions import ContentTypeError
import json
from typing import Union

# internal imports
from common import target_tomorrow, format_time


'''
    CREATE TABLE IF NOT EXISTS daily_quotes (
        author_id BIGINT PRIMARY KEY,
        start_time TIMESTAMP NOT NULL,
        target_time TIMESTAMP NOT NULL,
        is_dm BOOLEAN NOT NULL,
        server_id BIGINT,
        channel_id BIGINT
    )
'''


async def send_quote(destination: Union[discord.User, discord.TextChannel, commands.Context], bot, author_id: int = None) -> None:
    """Send a random quote to destination

    If an author_id is received, their daily quote's target time will be updated to the same time the following day.
    """
    params = {
        'lang': 'en',
        'method': 'getQuote',
        'format': 'json'
    }
    try:
        async with bot.session.get('http://api.forismatic.com/api/1.0/', params=params) as response:
            json_text = await response.json()
        quote, author = json_text['quoteText'], json_text['quoteAuthor']
        embed = discord.Embed(description=f'"{quote}"\n — {author}')
        await destination.send(embed=embed)
    except ContentTypeError as error:
        print(f'forismatic {error = }')
    except json.decoder.JSONDecodeError as error:
        print(f'forismatic {error = }')
    else:
        if author_id is not None:
            # Change the target time to tomorrow in the database.
            old_target_time = await bot.db.fetchval('''
                SELECT target_time
                FROM daily_quotes
                WHERE author_id = $1;
                ''', author_id)
            await update_quote_day(bot, author_id, old_target_time)


async def update_quote_day(bot, author_id: int, old_target_time: datetime) -> None:
    """Changes a daily quote's target datetime in the database to tomorrow"""
    new_target_time = await target_tomorrow(old_target_time)
    await bot.db.execute('''
        UPDATE daily_quotes
        SET target_time = $1
        WHERE author_id = $2
        ''', new_target_time, author_id)


class Quotes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.group(invoke_without_command=True)
    async def quote(self, ctx, daily_utc_time: str = ''):
        """Shows a random famous quote
        
        If a UTC time is provided in HH:mm format, a quote will be
        sent each day at that time. You can use the `time` command
        to see the current UTC time. You can cancel daily quotes
        with `quote stop`.
        """
        if not len(daily_utc_time):
            await send_quote(ctx, self.bot)
            return

        hour, minute = daily_utc_time.split(':')
        now = ctx.message.created_at
        target_time = datetime(now.year, now.month, now.day, int(hour), int(minute))
        if target_time < now:
            target_time = target_time + timedelta(days=1)

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
            DO
                UPDATE
                SET target_time = $3
                WHERE daily_quotes.author_id = $1;
            ''', ctx.author.id, now, target_time, is_dm, server_id, channel_id)

        daily_time = await format_time(target_time)
        await ctx.send(f'Time set! At {daily_time} UTC each day, I will send you a random quote.')
        await self.begin_daily_quote(ctx, target_time, ctx.author.id)


    @quote.command(name='stop')
    async def stop_daily_quote(self, ctx):
        """Stops your daily quotes"""
        try:
            await self.bot.db.execute('''
                DELETE FROM daily_quotes
                WHERE author_id = $1;
                ''', ctx.author.id)
        except Exception as e:
            print('sql delete from error: ', e)
        else:
            await ctx.send('Your daily quotes have been stopped.')


    @quote.command(name='mod-delete', aliases=['moddelete'])
    @commands.guild_only()
    @commands.has_guild_permissions(manage_messages=True)
    async def mod_delete_daily_quote(self, ctx, *, member: discord.Member):
        """Stops the daily quotes of anyone on this server"""
        try:
            await self.bot.db.execute('''
                DELETE FROM daily_quotes
                WHERE author_id = $1
                    AND server_id = $2;
                ''', member.id, ctx.guild.id)
        except Exception as e:
            await ctx.send(f'Error: {e}')
        else:
            await ctx.send(f"{member.display_name}'s daily quotes have been stopped.")


    async def begin_daily_quote(self, destination: Union[discord.User, discord.TextChannel, commands.Context], target_time: datetime, author_id: int) -> None:
        """Creates an asyncio task for a daily quote"""
        def error_callback(running_task):
            # Tasks fail silently without this function.
            if running_task.exception():
                running_task.print_stack()
        
        running_task = asyncio.create_task(self.daily_quote_loop(destination, self.bot, target_time, author_id))
        running_task.add_done_callback(error_callback)


    async def daily_quote_loop(self, destination: Union[discord.User, discord.TextChannel, commands.Context], bot, target_time: datetime, author_id: int) -> None:
        """Send a quote once a day at a specific time"""
        while True:
            now = datetime.utcnow()
            if now > target_time:
                date = now.date() + timedelta(days=1)
            else:
                date = now.date()
            target_time = datetime.combine(date, target_time.time())
            await discord.utils.sleep_until(target_time)
            await send_quote(destination, bot, author_id)


def setup(bot):
    bot.add_cog(Quotes(bot))