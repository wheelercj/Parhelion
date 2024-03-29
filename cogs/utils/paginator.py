import discord  # https://pypi.org/project/discord.py/
from discord.ext import commands  # https://pypi.org/project/discord.py/


class Paginator(discord.ui.View):
    """A paginator with interactive buttons.

    This paginator uses embeds. Currently, it may or may not fully support
    persistence.
    """

    def __init__(
        self,
        title: str,
        entries: list[str],
        *,
        length: int = 20,
        prefix: str = "",
        suffix: str = "",
        timeout: float = 180.0,
        filter_query: str | None = None,
        ephemeral: bool = False,
    ) -> None:
        """Creates a Paginator object.

        Parameters
        ----------
        title : str
            The title of the paginator.
        entries : list[str]
            The text to be paginated and displayed.
        length : int
            The number of entries to show on each page.
        prefix : str
            A string to prepend to each entry.
        suffix : str
            A string to append to each entry.
        timeout : float
            The number of seconds that the paginator's buttons should continue
            running for after the last interaction.
        filter_query : str | None
            A string for filtering entries. If the string is not present in an
            entry, that entry will not be shown. If no entries contain the
            filter query, commands.BadArgument will be raised with an
            appropriate description.
        ephemeral : bool
            Whether the output should be visible to only the person who requested the
            paginator.
        """
        super().__init__(timeout=timeout)
        self.title = title
        if not entries:
            raise AttributeError("There must be at least one entry.")
        self.entries = entries
        self.length = length
        self.prefix = prefix
        self.suffix = suffix
        self.filter_query = filter_query
        self.ephemeral = ephemeral
        self.pages: list[str] = self.create_pages()
        self.page_index = 0

    def create_pages(self) -> list[str]:
        filtered_entries: list[str] = []
        for entry in self.entries:
            if not self.filter_query or self.filter_query.lower() in entry.lower():
                filtered_entries.append(f"{self.prefix}{entry}{self.suffix}")
        if not filtered_entries:
            raise commands.BadArgument("No matches found.")
        result: list[str] = [
            "\n".join(filtered_entries[i : i + self.length])
            for i in range(0, len(filtered_entries), self.length)
        ]
        return result

    async def run(self, ctx) -> None:
        embed: discord.Embed = self.create_embed()
        if len(self.pages) == 1:
            self.message = await ctx.send(embed=embed, ephemeral=self.ephemeral)
            return
        await self.on_first_page()
        self.message = await ctx.send(embed=embed, view=self, ephemeral=self.ephemeral)

    async def on_timeout(self) -> None:
        await self.disable_all_buttons()
        await self.message.edit(view=self)

    @discord.ui.button(emoji="⏮", custom_id="persistent_view:go_to_first_page")
    async def go_to_first_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.page_index = 0
        await self.on_first_page()
        embed: discord.Embed = self.create_embed()
        return await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(emoji="◀", custom_id="persistent_view:go_to_previous_page")
    async def go_to_previous_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if self.page_index > 0:
            self.page_index -= 1
        await self.enable_all_buttons()
        if self.page_index == 0:
            await self.on_first_page()
        embed: discord.Embed = self.create_embed()
        return await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(emoji="▶", custom_id="persistent_view:go_to_next_page")
    async def go_to_next_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if self.page_index < len(self.pages) - 1:
            self.page_index += 1
        await self.enable_all_buttons()
        if self.page_index == len(self.pages) - 1:
            await self.on_last_page()
        embed: discord.Embed = self.create_embed()
        return await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(emoji="⏭", custom_id="persistent_view:go_to_last_page")
    async def go_to_last_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.page_index = len(self.pages) - 1
        await self.on_last_page()
        embed: discord.Embed = self.create_embed()
        return await interaction.response.edit_message(embed=embed, view=self)

    def create_embed(self) -> discord.Embed:
        embed = discord.Embed(title=self.title, description=self.pages[self.page_index])
        embed.set_footer(text=f"\u200b\npage {self.page_index + 1}/{len(self.pages)}")
        return embed

    async def enable_all_buttons(self) -> None:
        for child in self.children:
            child.disabled = False

    async def disable_all_buttons(self) -> None:
        for child in self.children:
            child.disabled = True

    async def on_last_page(self) -> None:
        for child in self.children[:2]:
            child.disabled = False
        for child in self.children[2:]:
            child.disabled = True

    async def on_first_page(self) -> None:
        for child in self.children[:2]:
            child.disabled = True
        for child in self.children[2:]:
            child.disabled = False
