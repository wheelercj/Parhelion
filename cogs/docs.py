import asyncpg  # https://pypi.org/project/asyncpg/
import discord  # https://pypi.org/project/discord.py/
from bs4 import BeautifulSoup  # https://pypi.org/project/beautifulsoup4/
from discord.ext import commands  # https://pypi.org/project/discord.py/

from cogs.utils.paginator import Paginator


class Docs(commands.Cog):
    """Browse documentation."""

    def __init__(self, bot):
        self.bot = bot
        self._task = bot.loop.create_task(self.load_docs_urls())
        self.docs_urls: dict[int, str] = dict()  # Server IDs and URLs.

    async def create_table_if_not_exists(self) -> None:
        await self.bot.db.execute(
            """
            CREATE TABLE IF NOT EXISTS docs (
                id SERIAL PRIMARY KEY,
                server_id BIGINT UNIQUE,
                url TEXT NOT NULL
            );
            """
        )

    async def load_docs_urls(self):
        await self.bot.wait_until_ready()
        await self.create_table_if_not_exists()
        try:
            records = await self.bot.db.fetch(
                """
                SELECT *
                FROM docs;
                """
            )
            for r in records:
                self.docs_urls[r["server_id"]] = r["url"]
        except (
            OSError,
            discord.ConnectionClosed,
            asyncpg.PostgresConnectionError,
        ) as error:
            print(f"{error = }")
            self._task.cancel()
            self._task = self.bot.loop.create_task(self.load_docs_urls())

    @commands.group(invoke_without_command=True)
    @commands.guild_only()
    async def doc(self, ctx, *, query: str = None):
        """A group of commands for searching documentation

        Without a subcommand, this command searches this server's chosen documentation.
        """
        doc_search_command = self.bot.get_command("doc search")
        await ctx.invoke(doc_search_command, query=query)

    @doc.command(name="search")
    @commands.guild_only()
    async def search_doc(self, ctx, *, query: str = None):
        """An alias for `doc`; searches this server's chosen documentation"""
        try:
            url = self.docs_urls[ctx.guild.id]
        except KeyError:
            raise commands.UserInputError(
                "This server hasn't chosen a ReadTheDocs URL for this command yet. If"
                ' you have the "manage server" permission, you can choose the URL with'
                " the `doc set` command."
            )
        if query is None:
            await ctx.send(f"<{url}>")
            return
        project_name, project_version, language, search_url = await self.parse_doc_url(
            url
        )
        params = {
            "q": query,
            "project": project_name,
            "version": project_version,
        }
        async with ctx.typing():
            async with self.bot.session.get(search_url, params=params) as response:
                if not response.ok:
                    raise ValueError(
                        f"API request failed with status code {response.status}."
                    )
                json_text = await response.json()
            result_pages = await self.parse_search_results(json_text, language)
            if not len(result_pages):
                raise commands.BadArgument("No matches found")
        paginator = Paginator(
            title=f"search results for `{query}`",
            entries=result_pages,
            length=3,
        )
        await paginator.run(ctx)

    @doc.command(name="set")
    @commands.has_guild_permissions(manage_guild=True)
    async def set_doc_url(self, ctx, url: str):
        """Sets the ReadTheDocs URL for the `doc` command for this server

        Currently, each server can only have one documentation URL.
        Here's an example of a valid URL: `https://discordpy.readthedocs.io/en/latest`
        """
        if "readthedocs" not in url:
            raise commands.BadArgument(
                "The `doc` commands only works with ReadTheDocs sites"
            )
        if not url.startswith("https://"):
            raise commands.BadArgument('ReadTheDocs URLs should begin with "https://"')
        if len(url.split("/")) < 5:
            raise commands.BadArgument(
                "The URL appears to be too short. Here's an example of a valid URL:"
                " `https://discordpy.readthedocs.io/en/latest`"
            )
        if len(url.split("/")[3]) != 2:
            raise commands.BadArgument(
                "The part of the URL that says the language of the documentation should"
                " be two letters long. Here's an example of a valid URL:"
                " `https://discordpy.readthedocs.io/en/latest`"
            )
        url = "/".join(url.split("/")[:5])
        self.docs_urls[ctx.guild.id] = url
        await self.bot.db.execute(
            """
            INSERT INTO docs
            (server_id, url)
            VALUES ($1, $2)
            ON CONFLICT (server_id)
            DO UPDATE
            SET url = $2
            WHERE docs.server_id = $1;
            """,
            ctx.guild.id,
            url,
        )
        await ctx.send(
            "The URL has been set! Everyone can now use the `doc` command with your"
            " chosen documentation source."
        )

    @doc.command(name="delete")
    @commands.has_guild_permissions(manage_guild=True)
    async def delete_doc_url(self, ctx):
        """Deletes this server's chosen URL for the `doc` command"""
        try:
            del self.docs_urls[ctx.guild.id]
        except KeyError:
            raise commands.UserInputError("No documentation URL had been set")
        await self.bot.db.execute(
            """
            DELETE FROM docs
            WHERE server_id = $1;
            """,
            ctx.guild.id,
        )
        await ctx.send("Documentation URL deleted")

    async def parse_doc_url(self, url: str) -> tuple[str, str, str, str]:
        """Split ReadTheDocs URL → project_name, project_version, language, & search_url

        E.g. 'https://discordpy.readthedocs.io/en/latest/index.html'
        becomes
        project_name = 'discordpy'
        project_version = 'latest'
        language = 'en'
        search_url = 'https://discordpy.readthedocs.io/_/api/v2/search/'
        """
        # Temporarily remove the `https://` or `http://` for easier parsing.
        i = url.find("//")
        url = url[i + 2 :]
        project_name = url.split(".")[0]
        project_version = url.split("/")[2]
        language = url.split("/")[1]
        search_url = "https://" + url.split("/")[0] + "/_/api/v2/search/"
        return project_name, project_version, language, search_url

    async def parse_search_results(
        self, json_text: str, language: str = None
    ) -> list[str]:
        """Formats doc search results for easy pagination"""
        result_pages = []
        for r in json_text["results"]:
            if language and language != r["path"][1:3]:
                continue
            results = ""
            title = r["title"]
            results_url = r["domain"] + r["path"]
            results += f"**[{title}]({results_url})**\n"
            for block in r["blocks"]:
                try:
                    section_title = f'**{block["title"]}**\n'
                except KeyError:
                    section_title = ""
                results += section_title
                for html_content in block["highlights"]["content"]:
                    # Convert the content from HTML to text.
                    soup = BeautifulSoup(html_content, features="html5lib")
                    content = soup.get_text()
                    results += f"• {content}\n"
            result_pages.append(results)
        return result_pages


async def setup(bot):
    await bot.add_cog(Docs(bot))
