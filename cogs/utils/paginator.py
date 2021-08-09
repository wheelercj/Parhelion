# external imports
import discord
from discord.ext import commands
from discord.ext import buttons


class Paginator(buttons.Paginator):
    """Paginator that uses an interactive session to display buttons

    title: str 
        Only available when embed=True. The title of the embeded pages. 
    length: int
        The number of entries per page. 
    entries: list
        The entries to paginate. 
    extra_pages: list
        Extra pages to append to our entries. 
    prefix: Optional[str] 
        The formatting prefix to apply to our entries. 
    suffix: Optional[str] 
        The formatting suffix to apply to our entries. 
    format: Optional[str] 
        The format string to wrap around our entries. This should be the first half of the format only, E.g to wrap Entry, we would only provide **. 
    colour: discord.Colour 
        Only available when embed=True. The colour of the embeded pages. 
    use_defaults: bool
        Option which determines whether we should use default buttons as well. This is True by default. 
    embed: bool
        Option that indicates that entries should be embeded. 
    joiner: str
        Option which allows us to specify the entries joiner. E.g self.joiner.join(self.entries) 
    timeout: int
        The timeout in seconds to wait for reaction responses. 
    thumbnail: 
        Only available when embed=True. The thumbnail URL to set for the embeded pages.
    """
    # buttons.Paginator repo: https://github.com/PythonistaGuild/buttons
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


    async def _paginate(self, ctx: commands.Context):
        if not self.entries and not self.extra_pages:
            raise AttributeError('You must provide atleast one entry or page for pagination.')  # ^^

        if self.entries:
            self.entries = [self.formatting(entry) for entry in self.entries]
            entries = list(self.chunker())
        else:
            entries = []

        for i, chunk in enumerate(entries):
            if not self.use_embed:
                self._pages.append(self.joiner.join(chunk))
            else:
                embed = discord.Embed(title=self.title, description=self.joiner.join(chunk), colour=self.colour)
                embed.set_footer(text=f'page {i+1}/{len(entries)}')

                if self.thumbnail:
                    embed.set_thumbnail(url=self.thumbnail)

                self._pages.append(embed)

        self._pages = self._pages + self.extra_pages

        if isinstance(self._pages[0], discord.Embed):
            self.page = await ctx.send(embed=self._pages[0])
        else:
            self.page = await ctx.send(self._pages[0])

        self._session_task = ctx.bot.loop.create_task(self._session(ctx))