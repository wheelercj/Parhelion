# external imports
import discord
from discord.ext import commands
from bs4 import BeautifulSoup


class Docs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.group()
    async def doc(self, ctx, *, query: str = None):
        """Searches this server's chosen documentation with a query"""
        if query is None:
            await ctx.send_help('doc')
            return

        url = 'https://docs.readthedocs.io/_/api/v2/search/'
        params = {
            'q': query,
            'project': 'docs',
            'version': 'latest',
            'page_size': 10,
        }
        async with ctx.typing():
            async with self.bot.session.get(url, params=params) as response:
                if not response.ok:
                    raise ValueError(f'API request failed with status code {response.status}.')
                json_text = await response.json()

            result_titles = ''
            for result in json_text['results']:
                result_url = result['domain'] + result['path']
                for result_title in result['highlights']['title']:
                    result_title = BeautifulSoup(result_title, features='html5lib').get_text()
                    result_titles += f'[{result_title}]({result_url})\n'

            if not len(result_titles):
                await ctx.send('No matches found')
                return

        title = f'search results for `{query}`'
        embed = discord.Embed(title=title, description=result_titles)
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Docs(bot))
