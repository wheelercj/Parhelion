from datetime import datetime
from datetime import timezone
from typing import Union

import discord  # https://pypi.org/project/discord.py/
from discord.ext import commands  # https://pypi.org/project/discord.py/

from cogs.utils.common import block_nsfw_channels
from cogs.utils.common import check_ownership_permission
from cogs.utils.common import DevSettings
from cogs.utils.paginator import Paginator


class Notes(commands.Cog):
    """Save and view your notes.

    For the notes commands that use indexes, use the numbers shown by the `notes`
    command.
    """

    def __init__(self, bot):
        self.bot = bot
        self._task = bot.loop.create_task(self.create_table_if_not_exists())
        self.note_ownership_limit = 5

    async def create_table_if_not_exists(self) -> None:
        await self.bot.wait_until_ready()
        await self.bot.db.execute(
            """
            CREATE TABLE IF NOT EXISTS notes (
                author_id BIGINT PRIMARY KEY,
                contents VARCHAR(500)[],
                jump_urls TEXT[],  -- The URLs to the messages that created the notes.
                -- This array is parallel to the contents array.
                last_viewed_at TIMESTAMPTZ NOT NULL
            );
            """
        )
        # Discord embed descriptions have a character limit of 4096 characters.
        # Each note has a 500 character limit.
        # The paginator in the notes command allows 7 notes in each embed.
        # 7 * 500 = 3500, so there's some extra space for indexes, URLs, etc.

    @commands.hybrid_command(aliases=["n", "todo"])
    async def note(self, ctx, *, text: str):
        """Creates a new note

        Use `help Notes` to learn more about the Notes commands.

        Parameters
        ----------
        text: str
            The content of the new note.
        """
        await block_nsfw_channels(ctx.channel)
        await self.check_note_ownership_permission(ctx.author)
        if len(text) > 500:
            raise commands.BadArgument(
                "Error: each note has a 500 character limit. This text is"
                f" {len(text)-500} characters over the limit."
            )
        try:
            _notes, jump_urls = await self.fetch_notes(ctx)
        except commands.BadArgument:
            _notes = []
            jump_urls = []
        _notes.append(text)
        if not ctx.interaction:
            jump_urls.append(ctx.message.jump_url)
        else:
            jump_urls.append(None)
        await self.save_notes(ctx, _notes, jump_urls)
        if ctx.interaction:
            await ctx.send(
                f"New note saved with an index of {len(_notes)}: {text}", ephemeral=True
            )
        else:
            await ctx.send(f"New note saved with an index of {len(_notes)}")

    @commands.hybrid_command(
        aliases=[
            "ns",
            "ln",
            "nl",
            "list-notes",
            "note-list",
            "notes-list",
            "listnotes",
            "notelist",
            "noteslist",
        ]
    )
    async def notes(self, ctx):
        """Shows your current notes"""
        _notes, jump_urls = await self.fetch_notes(ctx)
        for i, n in enumerate(_notes):
            if jump_urls[i]:
                _notes[i] = f"[**{i+1}**.]({jump_urls[i]}) {n}"
            else:
                _notes[i] = f"**{i+1}**. {n}"
        paginator = Paginator(
            title=f"{ctx.author.display_name}'s notes",
            entries=_notes,
            length=7,
            ephemeral=True,
        )
        await paginator.run(ctx)

    @commands.hybrid_command(name="edit-note", aliases=["en", "editnote"])
    async def edit_note(self, ctx, index: int, *, text: str):
        """Overwrites one of your existing notes

        Parameters
        ----------
        index: int
            The index of the note to edit.
        text: str
            The new content of the existing note.
        """
        await block_nsfw_channels(ctx.channel)
        i = index - 1
        if len(text) > 500:
            raise commands.BadArgument(
                "Each note has a 500 character limit."
                f" This note is {len(text)-500} characters over the limit."
            )
        _notes, jump_urls = await self.fetch_notes(ctx)
        await self.validate_note_indexes(_notes, i)
        _notes[i] = text
        if not ctx.interaction:
            jump_urls[i] = ctx.message.jump_url
        await self.save_notes(ctx, _notes, jump_urls)
        await ctx.send(f"Note {index} edited", ephemeral=True)

    @commands.hybrid_command(
        name="delete-note",
        aliases=["del-n", "deln", "del-note", "delnote", "deletenote"],
    )
    async def delete_note(self, ctx, index: int):
        """Deletes one of your notes

        Parameters
        ----------
        index: int
            The index of the note to delete.
        """
        i = index - 1
        _notes, jump_urls = await self.fetch_notes(ctx)
        await self.validate_note_indexes(_notes, i)
        try:
            _notes = _notes[:i] + _notes[i + 1 :]
            jump_urls = jump_urls[:i] + jump_urls[i + 1 :]
        except IndexError:
            _notes = _notes[:i]
            jump_urls = jump_urls[:i]
        if _notes:
            await self.bot.db.execute(
                """
                UPDATE notes
                SET contents = $1,
                    jump_urls = $2
                WHERE author_id = $3;
                """,
                _notes,
                jump_urls,
                ctx.author.id,
            )
        else:
            await self.bot.db.execute(
                """
                DELETE FROM notes
                WHERE author_id = $1;
                """,
                ctx.author.id,
            )
        await ctx.send(f"Deleted note {index}", ephemeral=True)

    @commands.hybrid_command(name="swap-notes", aliases=["sn", "swapnotes"])
    async def swap_notes(self, ctx, index_1: int, index_2: int):
        """Swaps the order of two of your notes

        Parameters
        ----------
        index_1: int
            The index of one of the notes to swap.
        index_2: int
            The index of another note to swap.
        """
        i = index_1 - 1
        j = index_2 - 1
        n, urls = await self.fetch_notes(ctx)
        await self.validate_note_indexes(n, i, j)
        await self._swap_notes(n, urls, i, j)
        await self.save_notes(ctx, n, urls)
        await ctx.send(f"Notes {i+1} and {j+1} swapped", ephemeral=True)

    @commands.hybrid_command(
        name="up-note", aliases=["un", "nu", "upnote", "note-up", "noteup"]
    )
    async def move_note_up(self, ctx, index: int):
        """Moves one of your notes up

        Parameters
        ----------
        index: int
            The index of one of your notes to move up in the list of notes.
        """
        swap_command = self.bot.get_command("swap-notes")
        await ctx.invoke(swap_command, index_1=index - 1, index_2=index)

    @commands.hybrid_command(
        name="down-note", aliases=["dn", "nd", "downnote", "note-down", "notedown"]
    )
    async def move_note_down(self, ctx, index: int):
        """Moves one of your notes down

        Parameters
        ----------
        index: int
            The index of one of your notes to move down in the list of notes.
        """
        swap_command = self.bot.get_command("swap-notes")
        await ctx.invoke(swap_command, index_1=index, index_2=index + 1)

    @commands.hybrid_command(
        name="top-note", aliases=["tn", "nt", "topnote", "note-top", "notetop"]
    )
    async def move_note_to_top(self, ctx, index: int):
        """Moves one of your notes to the top

        Parameters
        ----------
        index: int
            The index of one of your notes to the top of the list of notes.
        """
        swap_command = self.bot.get_command("swap-notes")
        await ctx.invoke(swap_command, index_1=1, index_2=index)

    @commands.hybrid_command(
        name="bottom-note",
        aliases=["bn", "nb", "bottomnote", "note-bottom", "notebottom"],
    )
    async def move_note_to_bottom(self, ctx, index: int):
        """Moves one of your notes to the bottom

        Parameters
        ----------
        index: int
            The index of one of your notes to move to the bottom of the list of notes.
        """
        n, _ = await self.fetch_notes(ctx)
        swap_command = self.bot.get_command("swap-notes")
        await ctx.invoke(swap_command, index_1=index, index_2=len(n))

    async def fetch_notes(self, ctx) -> tuple[list[str], list[str]]:
        """Gets ctx.author's notes & jump URLs from the db, & updates last_viewed_at

        Raises commands.BadArgument if ctx.author has no notes.
        """
        record = await self.bot.db.fetchrow(
            """
            UPDATE notes
            SET last_viewed_at = $1
            WHERE author_id = $2
            RETURNING *;
            """,
            datetime.now(timezone.utc),
            ctx.author.id,
        )
        if record is None:
            raise commands.BadArgument("You have no notes")
        return record["contents"], record["jump_urls"]

    async def save_notes(self, ctx, _notes, jump_urls) -> None:
        """Saves ctx.author's notes to the db, overwriting notes they already saved"""
        await self.bot.db.execute(
            """
            INSERT INTO notes
            (author_id, contents, jump_urls, last_viewed_at)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (author_id)
            DO UPDATE
            SET contents = $2,
                jump_urls = $3
            WHERE notes.author_id = $1;
            """,
            ctx.author.id,
            _notes,
            jump_urls,
            datetime.now(timezone.utc),
        )

    async def validate_note_indexes(
        self, _notes: list[str], *indexes: list[int]
    ) -> None:
        """Raises commands.BadArgument if an index is too low, high, or duplicated"""
        for i in indexes:
            if i < 0:
                raise commands.BadArgument("Please use a positive number")
            elif i >= len(_notes):
                raise commands.BadArgument("You do not have that many notes")
        if len(indexes) > 1:
            if indexes[0] == indexes[1]:
                raise commands.BadArgument("Please use two different indexes")

    async def _swap_notes(
        self, _notes: list[str], jump_urls: list[str], index_1: int, index_2: int
    ) -> None:
        """Swaps two notes; assumes the indexes are valid"""
        _notes[index_2], _notes[index_1] = _notes[index_1], _notes[index_2]
        jump_urls[index_2], jump_urls[index_1] = jump_urls[index_1], jump_urls[index_2]

    async def check_note_ownership_permission(
        self, author: Union[discord.User, discord.Member]
    ) -> None:
        """Raises commands.UserInputError if author has >= max # of notes allowed"""
        await check_ownership_permission(
            self.bot,
            author,
            "notes",
            DevSettings.membership_removes_note_limit,
            self.note_ownership_limit,
            self.count_users_notes,
        )

    async def count_users_notes(self, author_id: int) -> int:
        """Counts a user's current notes in the database"""
        records = await self.bot.db.fetch(
            """
            SELECT *
            FROM notes
            WHERE author_id = $1;
            """,
            author_id,
        )
        return len(records[0]["contents"]) if records else 0


async def setup(bot):
    await bot.add_cog(Notes(bot))
