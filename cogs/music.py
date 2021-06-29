# Source: https://github.com/Rapptz/discord.py/blob/v1.7.1/examples/basic_voice.py

# License:
# The MIT License (MIT)

# Copyright (c) 2015-present Rapptz

# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.


import asyncio
import discord
import youtube_dl
from discord.ext import commands
import discord.voice_client


# Suppress noise about console usage from errors
youtube_dl.utils.bug_reports_message = lambda: ''


ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0' # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')

        
    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        
    @commands.command()
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def join(self, ctx, *, channel: discord.VoiceChannel):
        """Joins a voice channel"""

        if ctx.voice_client is not None:
            return await ctx.voice_client.move_to(channel)

        await channel.connect()


    @join.error
    async def join_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send(f'Voice channel not found.')
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f'Missing argument: voice channel name.')


    # I don't want to allow downloading of audio files to repl.it, so this command can never be used anyways.   
    # @commands.command()
    # async def play(self, ctx, *, query):
    #   """Plays a file from the local filesystem"""

    #   source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(query))
    #   ctx.voice_client.play(source, after=lambda e: print('Player error: %s' % e) if e else None)

    #   await ctx.send('Now playing: {}'.format(query))


    # This command downloads files into repl.it, and the quality of the music it plays is terrible probably because of repl.it's limited resources.
    # @commands.command()
    # async def yt(self, ctx, *, url):
    #   """Plays from a url (almost anything youtube_dl supports)"""

    #   async with ctx.typing():
    #       player = await YTDLSource.from_url(url, loop=self.bot.loop)
    #       ctx.voice_client.play(player, after=lambda e: print('Player error: %s' % e) if e else None)

    #   await ctx.send('Now playing: {}'.format(player.title))

        
    @commands.command(aliases=['music', 'play'])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def stream(self, ctx, *, url):
        """Streams audio from a url"""

        async with ctx.typing():
            player = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True)
            ctx.voice_client.play(player, after=lambda e: print('Player error: %s' % e) if e else None)

        await ctx.send('Now playing: {}'.format(player.title))

        
    @commands.command()
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def volume(self, ctx, volume: int):
        """Changes the player's volume"""

        if ctx.voice_client is None:
            return await ctx.send('Not connected to a voice channel.')

        ctx.voice_client.source.volume = volume / 100
        await ctx.send('Changed volume to {}%'.format(volume))

        
    @commands.command()
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def stop(self, ctx):
        """Stops and disconnects the bot from voice"""
        await ctx.voice_client.disconnect()

        
    #@play.before_invoke
    #@yt.before_invoke
    @stream.before_invoke
    async def ensure_voice(self, ctx):
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send('You are not connected to a voice channel.')
                raise commands.CommandError('Author not connected to a voice channel.')
        elif ctx.voice_client.is_playing():
            ctx.voice_client.stop()


def setup(bot):
    bot.add_cog(Music(bot))
