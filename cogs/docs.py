# external imports
import discord
from discord.ext import commands
from bs4 import BeautifulSoup
from typing import Tuple, List

# internal imports
from common import Paginator


'''
CREATE TABLE docs (
    id SERIAL PRIMARY KEY,
    server_id BIGINT UNIQUE,
    url TEXT NOT NULL,
    language TEXT NOT NULL
);
'''


class Docs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.group()
    async def doc(self, ctx, *, query: str = None):
        """Searches this server's chosen documentation"""
        url = 'https://discordpy.readthedocs.io/en/latest/index.html'
        if 'readthedocs' not in url:
            raise commands.BadArgument('The `doc` commands only works with ReadTheDocs sites')
        if query is None:
            await ctx.send(f'<{url}>')
            return

        project_name, project_version, language, search_url = await self.parse_doc_url(url)
        params = {
            'q': query,
            'project': project_name,
            'version': project_version,
            'page_size': 20,
        }

        async with ctx.typing():
            async with self.bot.session.get(search_url, params=params) as response:
                if not response.ok:
                    raise ValueError(f'API request failed with status code {response.status}.')
                json_text = await response.json()

            result_pages = await self.parse_search_results(json_text, language)

            if not len(result_pages):
                await ctx.send('No matches found')
                return

        title = f'search results for `{query}`'
        paginator = Paginator(title=title, embed=True, timeout=90, use_defaults=True, entries=result_pages, length=3)
        await paginator.start(ctx)


    async def parse_doc_url(self, url: str) -> Tuple[str, str, str, str]:
        """Splits a ReadTheDocs URL into project_name, project_version, language, and search_url
        
        E.g. 'https://discordpy.readthedocs.io/en/latest/index.html'
        becomes
        project_name = 'discordpy'
        project_version = 'latest'
        language = 'en'
        search_url = 'https://discordpy.readthedocs.io/_/api/v2/search/'
        """
        # Temporarily remove the `https://` or `http://` for easier parsing.
        i = url.find('//')
        if i != -1:
            url = url[i+2:]
        project_name = url.split('.')[0]
        project_version = url.split('/')[2]
        language = url.split('/')[1]
        search_url = 'https://' + url.split('/')[0] + '/_/api/v2/search/'

        return project_name, project_version, language, search_url


    async def parse_search_results(self, json_text: str, language: str = None) -> List[str]:
        """Formats doc search results for easy pagination"""
        result_pages = []
        for i, r in enumerate(json_text['results']):
            if language and language != r['path'][1:3]:
                continue

            results = ''
            title = r['title']
            results_url = r['domain'] + r['path']
            results += f'**[{title}]({results_url})**\n'
            for block in r['blocks']:
                try:
                    section_title = f'**{block["title"]}**\n'
                except KeyError:
                    section_title = ''
                results += section_title
                for html_content in block['highlights']['content']:
                    # Convert the content from HTML to text.
                    soup = BeautifulSoup(html_content, features='html5lib')
                    content = soup.get_text()
                    results += f'• {content}\n'

            result_pages.append(results)

        return result_pages


def setup(bot):
    bot.add_cog(Docs(bot))
