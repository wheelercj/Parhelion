# external imports
from discord.ext import commands
from typing import List, Optional
from datetime import datetime, timezone

# internal imports
from cogs.utils.paginator import MyPaginator


'''
    CREATE TABLE notes (
        author_id BIGINT PRIMARY KEY,
        content VARCHAR(500)[],
        last_viewed_at TIMESTAMPTZ NOT NULL
    );
'''
# Discord embed descriptions have a character limit of 4096 characters.
# Each note has an 500 character limit.
# The paginator in the notes command allows 7 notes in each embed.
# 7 * 500 = 3500, so there's some extra space for indexes, URLs, etc.


class Notes(commands.Cog):
    """Save and view your notes.
    
    For the notes commands that use indexes, use the numbers shown by the `notes` command.
    """
    def __init__(self, bot):
        self.bot = bot


    @commands.command(aliases=['ns', 'ln', 'nl', 'list-notes', 'note-list', 'notes-list', 'listnotes', 'notelist', 'noteslist'])
    async def notes(self, ctx):
        """Shows your current notes"""
        _notes = await self.fetch_notes(ctx)
        for i, n in enumerate(_notes):
            _notes[i] = f'[**{i+1}**.](https://en.wikipedia.org/wiki/Array_data_structure) {n}'
        title = 'notes'
        paginator = MyPaginator(title=title, embed=True, timeout=90, use_defaults=True, entries=_notes, length=7)
        await paginator.start(ctx)


    @commands.command(aliases=['n'])
    async def note(self, ctx, *, text: str):
        """Creates a new note"""
        if len(text) > 500:
            raise commands.BadArgument('Each note has a 500 character limit.' \
                f' This note is {len(text)-500} characters over the limit.')

        try:
            _notes = await self.fetch_notes(ctx)
        except commands.BadArgument:
            _notes = []

        _notes.append(text)
        await self.save_notes(ctx, _notes)
        # await self.bot.db.execute('''
        #     INSERT INTO notes
        #     (author_id, content, last_viewed_at)
        #     VALUES ($1, $2, $3)
        #     ON CONFLICT (author_id)
        #     DO UPDATE
        #     SET content = array_append(content, $4)
        #     WHERE notes.author_id = $1;
        #     ''', ctx.author.id, [text], datetime.now(timezone.utc), text)

        await ctx.send('New note saved')


    @commands.command(name='delete-note', aliases=['del-n', 'deln', 'del-note', 'delnote', 'deletenote'])
    async def delete_note(self, ctx, index: int):
        """Deletes one of your notes"""
        i = index - 1
        _notes = await self.fetch_notes(ctx)
        await self.validate_note_indexes(_notes, i)
        
        try:
            _notes = _notes[:i] + _notes[i+1:]
        except IndexError:
            _notes = _notes[:i]

        if _notes:
            await self.bot.db.execute('''
                UPDATE notes
                SET content = $1
                WHERE author_id = $2;
                ''', _notes, ctx.author.id)
        else:
            await self.bot.db.execute('''
                DELETE FROM notes
                WHERE author_id = $1;
                ''', ctx.author.id)

        await ctx.send(f'Deleted note {index}')


    @commands.command(name='swap-notes', aliases=['sn', 'swapnotes'])
    async def swap_notes(self, ctx, index_1: int, index_2: int):
        """Swaps the order of two of your notes"""
        i = index_1 - 1
        j = index_2 - 1
        n = await self.fetch_notes(ctx)
        await self.validate_note_indexes(n, i, j)
        await self._swap_notes(n, i, j)
        await self.save_notes(ctx, n)
        await ctx.send(f'Notes {i+1} and {j+1} swapped')


    @commands.command(name='up-note', aliases=['un', 'nu', 'upnote', 'note-up', 'noteup'])
    async def move_note_up(self, ctx, index: int):
        """Moves one of your notes up"""
        swap_command = self.bot.get_command('swap-notes')
        await ctx.invoke(swap_command, index_1=index-1, index_2=index)


    @commands.command(name='down-note', aliases=['dn', 'nd', 'downnote', 'note-down', 'notedown'])
    async def move_note_down(self, ctx, index: int):
        """Moves one of your notes down"""
        swap_command = self.bot.get_command('swap-notes')
        await ctx.invoke(swap_command, index_1=index, index_2=index+1)


    @commands.command(name='top-note', aliases=['tn', 'nt', 'topnote', 'note-top', 'notetop'])
    async def move_note_to_top(self, ctx, index: int):
        """Moves one of your notes to the top"""
        swap_command = self.bot.get_command('swap-notes')
        await ctx.invoke(swap_command, index_1=1, index_2=index)


    @commands.command(name='bottom-note', aliases=['bn', 'nb', 'bottomnote', 'note-bottom', 'notebottom'])
    async def move_note_to_bottom(self, ctx, index: int):
        """Moves one of your notes to the bottom"""
        n = await self.fetch_notes(ctx)
        swap_command = self.bot.get_command('swap-notes')
        await ctx.invoke(swap_command, index_1=index, index_2=len(n))


    async def fetch_notes(self, ctx) -> Optional[List[str]]:
        """Gets ctx.author's notes from the database and updates last_viewed_at
        
        Raises commands.BadArgument if ctx.author has no notes.
        """
        _notes: List[str] = await self.bot.db.fetchval('''
            UPDATE notes
            SET last_viewed_at = $1
            WHERE author_id = $2
            RETURNING content;
            ''', datetime.now(timezone.utc), ctx.author.id)
        if _notes is None or not len(_notes):
            raise commands.BadArgument('You have no notes')

        return _notes


    async def save_notes(self, ctx, _notes) -> None:
        """Saves ctx.author's notes to the database, overwriting any notes they already have saved there"""
        await self.bot.db.execute('''
            INSERT INTO notes
            (author_id, content, last_viewed_at)
            VALUES ($1, $2, $3)
            ON CONFLICT (author_id)
            DO UPDATE
            SET content = $2
            WHERE notes.author_id = $1;
            ''', ctx.author.id, _notes, datetime.now(timezone.utc))


    async def validate_note_indexes(self, _notes: List[str], *indexes: List[int]) -> None:
        """Raises commands.BadArgument if any index is to low or to high, or if there's a duplicate index"""
        for i in indexes:
            if i < 0:
                raise commands.BadArgument('Please use a positive number')
            elif i >= len(_notes):
                raise commands.BadArgument('You do not have that many notes')
        if len(indexes) == 2:
            if indexes[0] == indexes[1]:
                raise commands.BadArgument('Please use two different indexes')


    async def _swap_notes(self, _notes: List[str], index_1: int, index_2: int) -> None:
        """Swaps two notes; does not validate indexes"""
        _notes[index_2], _notes[index_1] = _notes[index_1], _notes[index_2]


def setup(bot):
    bot.add_cog(Notes(bot))
