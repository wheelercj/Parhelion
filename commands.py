import os
import discord
from discord.ext import commands


my_discord_user_id = int(os.environ['MY_DISCORD_USER_ID'])
my_channel_id = int(os.environ['MY_CHANNEL_ID'])
bot = commands.Bot(command_prefix=';')


@bot.command(hidden=True)
async def echo(context, *, message: str):
	'''Repeats a message'''
	await context.send(message)


@bot.command(hidden=True)
async def ping(context):
	'''Pings the server'''
	await context.send(f'Pong! It took {round(bot.latency, 2)} ms.')


@bot.command(aliases=['about'])
async def info(context):
	'''Shows general info about this bot'''
	embed = discord.Embed(description='Enter `;help` for a list of commands.\nThis bot was created by Chris Wheeler, except for the parts otherwise specified. See the source on Repl.it by clicking [here](https://replit.com/@wheelercj/simple-Discord-bot).')
	await context.send(embed=embed)


@bot.command()
async def invite(context):
	'''Shows the link to invite this bot to another server'''
	await context.send('You can invite me to another server that you have "manage server" permissions in with this link: https://discordapp.com/api/oauth2/authorize?scope=bot&client_id=836071320328077332&permissions=3300352')


@bot.command(aliases=['py', 'python', 'eval'])
async def calc(context, *, string: str):
    '''Evaluates math expressions'''
    try:
        if i_am_the_dev(context):
            await context.send(eval(string))
        else:
            # The eval function can do just about anything by default, so a
            # lot of its features have to be removed for security. For more
            # info, see https://realpython.com/python-eval-function/#minimizing-the-security-issues-of-eval
            allowed_names = {}
            code = compile(string, '<string>', 'eval')
            for name in code.co_names:
                if name not in allowed_names:
                    raise NameError(f'Use of "{name}" is not allowed.')

            await context.send(eval(code, {"__builtins__": {}}, allowed_names))
    except NameError as e:
        await context.send(e)
    except Exception as e:
        await context.send(f'Python error: {e}')


def i_am_the_dev(context):
	if context.author.id == my_discord_user_id:
		return True
	return False


async def dev_mail(bot, message):
	channel = await bot.fetch_channel(my_channel_id)
	embed = discord.Embed(title='dev mail', description=message)
	await channel.send(embed=embed)


@bot.command(hidden=True)
async def reverse(context, *, message: str):
	'''Reverses a message'''
	await context.send(message[::-1])


@bot.command(hidden=True)
async def rot13(context, *, message: str):
	'''Rotates each letter of a message 13 letters through the alphabet'''
	message = message.lower()
	new_string = ''
	alphabet = 'abcdefghijklmnopqrstuvwxyz'
	for char in message:
		index = alphabet.find(char)
		if index != -1:
			new_index = (index + 13) % 26
			new_string += alphabet[new_index]
		else:
			new_string += char

	await context.send(new_string)


@bot.command()
async def servers(context):
	'''Shows how many servers this bot is in'''
	await context.send(f'I am in {len(bot.guilds)} servers.')


@bot.command(hidden=True)
async def leave(context):
	'''Makes the bot leave the server'''
	if not i_am_the_dev(context):
		await context.send(f'Access to the leave command denied. Server administrators should still be able to remove any bot.')
	else:
		await context.send(f'Now leaving the server. Goodbye!')
		await context.guild.leave()
