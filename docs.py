from commands import *
import discord


docs = {
	'inspect': '''A Python module for getting info about live objects such as modules, classes, methods, functions, tracebacks, frame objects, and code objects. Some of its functions: getdoc, getcomments, getmodule, getsource.
	More details: https://docs.python.org/3/library/inspect.html''',

	'discord.py': '''Homepage: https://discordpy.readthedocs.io/en/latest/index.html
	Discord server: https://discord.gg/r3sSKJJ'''
}


@bot.command(aliases=['listdocs'])
async def docs(context):
	'''Lists the names of all docs'''
	doc_names = ''
	for doc_name in docs.keys():
		doc_names += f'\n{doc_name}'
	embed = discord.Embed(title='doc names', description=doc_names)
	await context.send(embed=embed)


@bot.command()
async def doc(context, *, name: str):
	'''Shows info about a topic'''
	try:
		embed = discord.Embed(title=name, description=docs[name])
		await context.send(embed=embed)
	except KeyError:
		await context.send(f'Could not find `{name}`.')
