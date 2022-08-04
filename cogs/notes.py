from datetime import datetime
from datetime import timezone
from typing import List
from typing import Optional
from typing import Tuple

from discord.ext import commands  # https://pypi.org/project/discord.py/

from cogs.utils.common import block_nsfw_channels
from cogs.utils.paginator import MyPaginator


"""
    CREATE TABLE notes (
        author_id BIGINT PRIMARY KEY,
        contents VARCHAR(500)[],
        jump_urls TEXT[],  -- The URLs to the messages in which the notes were created. This array is parallel to the contents array.
        last_viewed_at TIMESTAMPTZ NOT NULL
    );
"""
# Discord embed descriptions have a character limit of 4096 characters.
# Each note has a 500 character limit.
# The paginator in the notes command allows 7 notes in each embed.
# 7 * 500 = 3500, so there's some extra space for indexes, URLs, etc.


class Notes(commands.Cog):
    """Save and view your notes.

    For the notes commands that use indexes, use the numbers shown by the `notes` command.
    """

    def __init__(self, bot):
        self.bot = bot
        self.note_ownership_limit = 20

    @commands.command(
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
            _notes[i] = f"[**{i+1}**.]({jump_urls[i]}) {n}"

        embed_title = f"{ctx.author.display_name}'s notes"
        paginator = MyPaginator(
            title=embed_title,
            embed=True,
            timeout=90,
            use_defaults=True,
            entries=_notes,
            length=7,
        )
        await paginator.start(ctx)

    @commands.command(aliases=["n", "todo"])
    async def note(self, ctx, *, text: str):
        """Creates a new note

        Use `help Notes` to learn more about the Notes commands.
        """
        await block_nsfw_channels(ctx.channel)
        await self.check_note_ownership_permission(ctx.author.id)
        if len(text) > 500:
            raise commands.BadArgument(
                "Each note has a 500 character limit."
                f" This note is {len(text)-500} characters over the limit."
            )

        try:
            _notes, jump_urls = await self.fetch_notes(ctx)
        except commands.BadArgument:
            _notes = []
            jump_urls = []
        _notes.append(text)
        jump_urls.append(ctx.message.jump_url)
        await self.save_notes(ctx, _notes, jump_urls)
        await ctx.send("New note saved")

    @commands.command(name="edit-note", aliases=["en", "editnote"])
    async def edit_note(self, ctx, index: int, *, text: str):
        """Overwrites one of your existing notes"""
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
        jump_urls[i] = ctx.message.jump_url
        await self.save_notes(ctx, _notes, jump_urls)
        await ctx.send(f"Note {index} edited")

    @commands.command(
        name="delete-note",
        aliases=["del-n", "deln", "del-note", "delnote", "deletenote"],
    )
    async def delete_note(self, ctx, index: int):
        """Deletes one of your notes"""
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

        await ctx.send(f"Deleted note {index}")

    @commands.command(name="swap-notes", aliases=["sn", "swapnotes"])
    async def swap_notes(self, ctx, index_1: int, index_2: int):
        """Swaps the order of two of your notes"""
        i = index_1 - 1
        j = index_2 - 1
        n, urls = await self.fetch_notes(ctx)
        await self.validate_note_indexes(n, i, j)
        await self._swap_notes(n, urls, i, j)
        await self.save_notes(ctx, n, urls)
        await ctx.send(f"Notes {i+1} and {j+1} swapped")

    @commands.command(
        name="up-note", aliases=["un", "nu", "upnote", "note-up", "noteup"]
    )
    async def move_note_up(self, ctx, index: int):
        """Moves one of your notes up"""
        swap_command = self.bot.get_command("swap-notes")
        await ctx.invoke(swap_command, index_1=index - 1, index_2=index)

    @commands.command(
        name="down-note", aliases=["dn", "nd", "downnote", "note-down", "notedown"]
    )
    async def move_note_down(self, ctx, index: int):
        """Moves one of your notes down"""
        swap_command = self.bot.get_command("swap-notes")
        await ctx.invoke(swap_command, index_1=index, index_2=index + 1)

    @commands.command(
        name="top-note", aliases=["tn", "nt", "topnote", "note-top", "notetop"]
    )
    async def move_note_to_top(self, ctx, index: int):
        """Moves one of your notes to the top"""
        swap_command = self.bot.get_command("swap-notes")
        await ctx.invoke(swap_command, index_1=1, index_2=index)

    @commands.command(
        name="bottom-note",
        aliases=["bn", "nb", "bottomnote", "note-bottom", "notebottom"],
    )
    async def move_note_to_bottom(self, ctx, index: int):
        """Moves one of your notes to the bottom"""
        n, _ = await self.fetch_notes(ctx)
        swap_command = self.bot.get_command("swap-notes")
        await ctx.invoke(swap_command, index_1=index, index_2=len(n))

    async def fetch_notes(self, ctx) -> Optional[Tuple[List[str], List[str]]]:
        """Gets ctx.author's notes and their jump URLs from the database, and updates last_viewed_at

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
        """Saves ctx.author's notes to the database, overwriting any notes they already have saved there"""
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
        self, _notes: List[str], *indexes: List[int]
    ) -> None:
        """Raises commands.BadArgument if any index is to low or to high, or if this receives any duplicate indexes"""
        for i in indexes:
            if i < 0:
                raise commands.BadArgument("Please use a positive number")
            elif i >= len(_notes):
                raise commands.BadArgument("You do not have that many notes")
        if len(indexes) > 1:
            if indexes[0] == indexes[1]:
                raise commands.BadArgument("Please use two different indexes")

    async def _swap_notes(
        self, _notes: List[str], jump_urls: List[str], index_1: int, index_2: int
    ) -> None:
        """Swaps two notes; assumes the indexes are valid"""
        _notes[index_2], _notes[index_1] = _notes[index_1], _notes[index_2]
        jump_urls[index_2], jump_urls[index_1] = jump_urls[index_1], jump_urls[index_2]

    async def check_note_ownership_permission(self, author_id: int) -> None:
        """Raises commands.UserInputError if the author has >= the maximum number of notes allowed"""
        members_note_count = await self.count_users_notes(author_id)
        if (
            members_note_count >= self.note_ownership_limit
            and self.bot.owner_id != author_id  # noqa: W503
        ):
            raise commands.UserInputError(
                f"The current limit to how many notes each person can have is {self.note_ownership_limit}."
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
        if records:
            return len(records)
        return 0


def setup(bot):
    bot.add_cog(Notes(bot))
