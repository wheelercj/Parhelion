# Source: https://github.com/Rapptz/discord.py/blob/v1.7.1/examples/basic_voice.py
import asyncio
import discord
import youtube_dl
from discord.ext import commands
import discord.voice_client
from commands import *


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
	async def join(self, context, *, channel: discord.VoiceChannel):
		'''Joins a voice channel'''

		if context.voice_client is not None:
			return await context.voice_client.move_to(channel)

		await channel.connect()

		
	@commands.command()
	async def play(self, context, *, query):
		'''Plays a file from the local filesystem'''

		source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(query))
		context.voice_client.play(source, after=lambda e: print('Player error: %s' % e) if e else None)

		await context.send('Now playing: {}'.format(query))

		
	@commands.command()
	async def yt(self, context, *, url):
		'''Plays from a url (almost anything youtube_dl supports)'''

		async with context.typing():
			player = await YTDLSource.from_url(url, loop=self.bot.loop)
			context.voice_client.play(player, after=lambda e: print('Player error: %s' % e) if e else None)

		await context.send('Now playing: {}'.format(player.title))

		
	@commands.command()
	async def stream(self, context, *, url):
		'''Streams from a url (same as yt, but doesn't predownload)'''

		async with context.typing():
			player = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True)
			context.voice_client.play(player, after=lambda e: print('Player error: %s' % e) if e else None)

		await context.send('Now playing: {}'.format(player.title))

		
	@commands.command()
	async def volume(self, context, volume: int):
		'''Changes the player's volume'''

		if context.voice_client is None:
			return await context.send('Not connected to a voice channel.')

		context.voice_client.source.volume = volume / 100
		await context.send('Changed volume to {}%'.format(volume))

		
	@commands.command()
	async def stop(self, context):
		'''Stops and disconnects the bot from voice'''
		await context.voice_client.disconnect()

		
	@play.before_invoke
	@yt.before_invoke
	@stream.before_invoke
	async def ensure_voice(self, context):
		if context.voice_client is None:
			if context.author.voice:
				await context.author.voice.channel.connect()
			else:
				await context.send('You are not connected to a voice channel.')
				raise commands.CommandError('Author not connected to a voice channel.')
		elif context.voice_client.is_playing():
			context.voice_client.stop()


bot.add_cog(Music(bot))