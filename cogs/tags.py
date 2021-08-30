# external imports
import discord
from discord.ext import commands
import asyncpg
import io
from typing import Optional, List
from datetime import datetime, timezone

# internal imports
from cogs.utils.io import split_input, get_attachment_url
from cogs.utils.time import create_relative_timestamp
from cogs.utils.paginator import MyPaginator
from cogs.utils.common import plural


'''
    CREATE TABLE tags (
        id SERIAL PRIMARY KEY,
        name VARCHAR(50) NOT NULL,
        parent_tag_id INT,
        content VARCHAR(1500),
        file_url TEXT,
        created TIMESTAMPTZ NOT NULL,
        owner_id BIGINT NOT NULL,
        server_id BIGINT NOT NULL,
        views INT DEFAULT 0,
        UNIQUE (name, server_id)
    );
'''
# Either parent_tag_id is NULL, or content and file_url are both NULL
# (though either content or file_url may be NULL regardless).


class Tags(commands.Cog):
    """Save and share messages such as FAQs."""
    def __init__(self, bot):
        self.bot = bot
        self.tag_ownership_limit = 20
        self.tag_name_length_limit = 50
        self.tag_content_length_limit = 1500


    async def cog_check(self, ctx):
        if not ctx.guild:
            raise commands.NoPrivateMessage
        return True


    @commands.group(invoke_without_command=True)
    async def tag(self, ctx, *, tag_name: str):
        """A group of commands for creating and viewing tags
        
        Without a subcommand, this command finds and shows a tag's contents.
        You can use tags to quickly save and share messages, such as for FAQs.
        Tags can be viewed by anyone on this server, but not other servers.
        """
        view_tag_command = self.bot.get_command('tag view')
        await ctx.invoke(view_tag_command, tag_name=tag_name)


    @tag.command(name='view', aliases=['v'])
    async def view_tag(self, ctx, *, tag_name: str):
        """An alias for `tag`; finds and shows a tag's contents"""
        record = await self.bot.db.fetchrow('''
            UPDATE tags
            SET views = views + 1
            WHERE LOWER(name) = LOWER($1)
                AND server_id = $2
            RETURNING *;
            ''', tag_name, ctx.guild.id)
        await self.send_tag_contents(ctx, record)


    @tag.command(name='create', aliases=['c'])
    async def create_tag(self, ctx, *, name_and_content: str):
        """Creates a new tag

        If the tag name has spaces, surround it with double quotes. If the tag has an attachment, the message in which the tag was created must not be deleted, or the attachment will be lost.
        """
        await self.check_tag_ownership_permission(ctx, ctx.author)
        name, content = await split_input(name_and_content)
        await self.validate_new_tag_info(name, content, ctx.guild.id)
        now = datetime.now(timezone.utc)
        file_url = await get_attachment_url(ctx)

        try:
            await self.bot.db.execute('''
                INSERT INTO tags
                (name, content, file_url, created, owner_id, server_id)
                VALUES ($1, $2, $3, $4, $5, $6)
                ''', name, content, file_url, now, ctx.author.id, ctx.guild.id)
            
            await ctx.send(f'Successfully created tag "{name}"')
        except asyncpg.exceptions.UniqueViolationError:
            await ctx.send(f'A tag named "{name}" already exists.')


    @tag.command(name='list', aliases=['l'])
    async def list_tags(self, ctx, member: discord.Member = None):
        """Lists the names of yours or someone else's tags on this server"""
        if member is None:
            member = ctx.author

        records = await self.bot.db.fetch('''
            SELECT *
            FROM tags
            WHERE owner_id = $1
                AND server_id = $2;
            ''', member.id, ctx.guild.id)

        if not records or not len(records):
            raise commands.BadArgument(f'{member.name}#{member.discriminator} has no tags on this server.')

        title = f"{member.name}#{member.discriminator}'s tags"
        await self.paginate_tag_list(ctx, title, records)


    @commands.command(hidden=True)
    async def tags(self, ctx, member: discord.Member = None):
        """Lists the names of yours or someone else's tags on this server; this is an alias for `tag list`"""
        tag_list_command = self.bot.get_command('tag list')
        await ctx.invoke(tag_list_command, member=member)


    @tag.command(name='info', aliases=['i'])
    async def tag_info(self, ctx, *, tag_name: str):
        """Shows info about a tag"""
        record = await self.bot.db.fetchrow('''
            SELECT *
            FROM tags
            WHERE LOWER(name) = LOWER($1)
                AND server_id = $2;
            ''', tag_name, ctx.guild.id)

        await self.send_tag_info(ctx, record)


    @tag.command(name='edit', aliases=['e'])
    async def edit_tag(self, ctx, *, name_and_content: str):
        """Rewrites one of your tags

        If the tag has an attachment, the message in which the tag was edited must not be deleted, or the attachment will be lost.
        """
        tag_name, content = await split_input(name_and_content)
        await self.validate_new_tag_info(tag_name, content, ctx.guild.id)

        record = await self.bot.db.fetchrow('''
            SELECT *
            FROM tags
            WHERE LOWER(name) = LOWER($1)
                AND owner_id = $2
                AND server_id = $3;
            ''', tag_name, ctx.author.id, ctx.guild.id)
        if record is None:
            raise commands.BadArgument('Tag not found.')
        if record['parent_tag_id']:
            raise commands.BadArgument('You cannot edit a tag alias.')

        await self.handle_tag_edit(ctx, record, content)


    @tag.command(name='delete', aliases=['del'])
    async def delete_tag(self, ctx, *, tag_name: str):
        """Deletes one of your tags (or aliases) and all aliases it may have"""
        record = await self.bot.db.fetchrow('''
            DELETE FROM tags
            WHERE LOWER(name) = LOWER($1)
                AND owner_id = $2
                AND server_id = $3
            RETURNING *;
            ''', tag_name, ctx.author.id, ctx.guild.id)
        await self.handle_tag_cleanup(ctx, record)


    @tag.command(name='mod-delete', aliases=['mdel', 'moddelete'])
    @commands.has_guild_permissions(manage_messages=True)
    async def mod_delete_tag(self, ctx, *, tag_name: str):
        """Deletes one of anyone's tags (or aliases) and all aliases it may have"""
        record = await self.bot.db.fetchrow('''
            DELETE FROM tags
            WHERE LOWER(name) = LOWER($1)
                AND server_id = $2
            RETURNING *;
            ''', tag_name, ctx.guild.id)
        await self.handle_tag_cleanup(ctx, record)


    @tag.command(name='claim', aliases=['cl'])
    async def claim_tag(self, ctx, *, tag_name: str):
        """Gives you ownership of a tag if its owner left the server"""
        await self.check_tag_ownership_permission(ctx, ctx.author)

        record = await self.bot.db.fetchrow('''
            SELECT *
            FROM tags
            WHERE LOWER(name) = LOWER($1)
                AND server_id = $2;
            ''', tag_name, ctx.guild.id)
        if record is None:
            raise commands.BadArgument('Tag not found.')
        if record['owner_id'] == ctx.author.id:
            raise commands.BadArgument('This tag already belongs to you.')
        owner = ctx.guild.get_member(record['owner_id'])
        if owner is not None:
            raise commands.BadArgument("The tag's owner is still in this server.")

        await self.handle_tag_transfer(ctx, record, ctx.author)


    @tag.command(name='transfer', aliases=['t'])
    async def transfer_tag(self, ctx, member: discord.Member, *, tag_name: str):
        """Gives a server member ownership of one of your tags"""
        await self.check_tag_ownership_permission(ctx, member)

        record = await self.bot.db.fetchrow('''
            SELECT *
            FROM tags
            WHERE LOWER(name) = LOWER($1)
                AND server_id = $2;
            ''', tag_name, ctx.guild.id)
        if record is None:
            raise commands.BadArgument('Tag not found.')
        if record['owner_id'] != ctx.author.id:
            raise commands.BadArgument('This tag does not belong to you.')

        await self.handle_tag_transfer(ctx, record, member)


    @tag.command(name='raw', aliases=['r'])
    async def get_raw_tag(self, ctx, *, tag_name: str):
        """Shows the unrendered text content of a tag"""
        record = await self.bot.db.fetchrow('''
            UPDATE tags
            SET views = views + 1
            WHERE LOWER(name) = LOWER($1)
                AND server_id = $2
            RETURNING *;
            ''', tag_name, ctx.guild.id)
        await self.send_tag_contents(ctx, record, send_raw=True)


    @tag.command(name='search', aliases=['s'])
    async def tag_search(self, ctx, *, query: str):
        """Searches for a tag on this server by name"""
        if len(query) < 3:
            raise commands.BadArgument('Please enter a query that is at least 3 characters long.')
            # Postgres searches simply do not work with fewer characters for some reason.

        records = await self.bot.db.fetch('''
            SELECT *
            FROM (SELECT *,
                    to_tsvector(tags.name) as document
                  FROM tags
                  WHERE server_id = $1) tag_search
            WHERE tag_search.document @@ to_tsquery($2);
            ''', ctx.guild.id, query)

        if not records or not len(records):
            raise commands.BadArgument(f'No matches found.')

        await self.paginate_tag_list(ctx, '', records)


    @tag.command(name='all', aliases=['a'])
    async def list_all_tags(self, ctx):
        """Lists all tags on this server"""
        records = await self.bot.db.fetch('''
            SELECT *
            FROM tags
            WHERE server_id = $1;
            ''', ctx.guild.id)

        if not records or not len(records):
            raise commands.UserInputError(f'There are no tags on this server.')

        await self.paginate_tag_list(ctx, '', records)

    
    @tag.command(name='alias')
    async def create_tag_alias(self, ctx, existing_tag_name: str, *, new_alias: str):
        """Creates another name for an existing tag"""
        await self.check_tag_ownership_permission(ctx, ctx.author)
        await self.validate_new_tag_info(new_alias, server_id=ctx.guild.id)

        record = await self.bot.db.fetchrow('''
            SELECT *
            FROM tags
            WHERE LOWER(name) = LOWER($1)
                AND server_id = $2;
            ''', existing_tag_name, ctx.guild.id)

        await self.handle_tag_alias_creation(ctx, record, new_alias)


    @tag.command(name='stats', hidden=True)
    async def tag_stats(self, ctx):
        """Shows tag statistics about a member or the server"""
        # TODO
        await ctx.send('This command is under construction.')


    @tag.command(name='make', hidden=True)
    async def make_tag(self, ctx):
        """Interactively helps you create a tag"""
        # TODO
        await ctx.send('This command is under construction.')


########################
# tag_ID command group #
########################


    @tag.group(name='id')
    async def tag_id(self, ctx, tag_ID: int = None):
        """A group of commands using tag IDs instead of tag names
        
        Without a subcommand, this command finds and shows a tag's contents.
        """
        view_tag_by_id_command = self.bot.get_command('tag id view')
        await ctx.invoke(view_tag_by_id_command, tag_ID=tag_ID)


    @tag_id.command(name='view', aliases=['v'])
    async def view_tag_by_id(self, ctx, tag_ID: int = None):
        """An alias for `tag id`; finds and shows a tag's contents"""
        if tag_ID is None:
            await ctx.send_help('tag id')
            return

        record = await self.bot.db.fetchrow('''
            UPDATE tags
            SET views = views + 1
            WHERE id = $1
                AND server_id = $2
            RETURNING *;
            ''', tag_ID, ctx.guild.id)

        await self.send_tag_contents(ctx, record)


    @tag_id.command(name='info', aliases=['i'])
    async def tag_info_by_id(self, ctx, tag_ID: int):
        """Shows info about a tag"""
        record = await self.bot.db.fetchrow('''
            SELECT *
            FROM tags
            WHERE id = $1
                AND server_id = $2;
            ''', tag_ID, ctx.guild.id)

        await self.send_tag_info(ctx, record)


    @tag_id.command(name='edit', aliases=['e'])
    async def edit_tag_by_id(self, ctx, tag_ID: int, *, new_content: str):
        """Rewrites one of your tags

        If the tag has an attachment, the message in which the tag was edited must not be deleted, or the attachment will be lost.
        """
        await self.validate_new_tag_info(content=new_content)

        record = await self.bot.db.fetchrow('''
            SELECT *
            FROM tags
            WHERE id = $1
                AND owner_id = $2
                AND server_id = $3;
            ''', tag_ID, ctx.author.id, ctx.guild.id)
        if record is None:
            raise commands.BadArgument('Tag not found.')
        if record['parent_tag_id']:
            raise commands.BadArgument('You cannot edit a tag alias.')

        await self.handle_tag_edit(ctx, record, new_content)


    @tag_id.command(name='delete', aliases=['del'])
    async def delete_tag_by_id(self, ctx, tag_ID: int):
        """Deletes one of your tags (or aliases) and all aliases it may have"""
        record = await self.bot.db.fetchrow('''
            DELETE FROM tags
            WHERE id = $1
                AND owner_id = $2
                AND server_id = $3
            RETURNING *;
            ''', tag_ID, ctx.author.id, ctx.guild.id)
        await self.handle_tag_cleanup(ctx, record)


    @tag_id.command(name='mod-delete', aliases=['mdel', 'moddelete'])
    @commands.has_guild_permissions(manage_messages=True)
    async def mod_delete_tag_by_id(self, ctx, tag_ID: int):
        """Deletes one of anyone's tags (or aliases) and all aliases it may have"""
        record = await self.bot.db.fetchrow('''
            DELETE FROM tags
            WHERE id = $1
                AND server_id = $2
            RETURNING *;
            ''', tag_ID, ctx.guild.id)
        await self.handle_tag_cleanup(ctx, record)


    @tag_id.command(name='claim', aliases=['cl'])
    async def claim_tag_by_id(self, ctx, tag_ID: int):
        """Gives you ownership of a tag if its owner left the server"""
        await self.check_tag_ownership_permission(ctx, ctx.author)

        record = await self.bot.db.fetchrow('''
            SELECT *
            FROM tags
            WHERE id = $1
                AND server_id = $2;
            ''', tag_ID, ctx.guild.id)
        if record is None:
            raise commands.BadArgument('Tag not found.')
        if record['owner_id'] == ctx.author.id:
            raise commands.BadArgument('This tag already belongs to you.')
        owner = ctx.guild.get_member(record['owner_id'])
        if owner is not None:
            raise commands.BadArgument("The tag's owner is still in this server.")

        await self.handle_tag_transfer(ctx, record, ctx.author)


    @tag_id.command(name='transfer', aliases=['t'])
    async def transfer_tag_by_id(self, ctx, member: discord.Member, tag_ID: int):
        """Gives a server member ownership of one of your tags"""
        await self.check_tag_ownership_permission(ctx, member)

        record = await self.bot.db.fetchrow('''
            SELECT *
            FROM tags
            WHERE id = $1
                AND server_id = $2;
            ''', tag_ID, ctx.guild.id)
        if record is None:
            raise commands.BadArgument('Tag not found.')
        if record['owner_id'] != ctx.author.id:
            raise commands.BadArgument('This tag does not belong to you.')

        await self.handle_tag_transfer(ctx, record, member)


    @tag_id.command(name='raw', aliases=['r'])
    async def get_raw_tag_by_id(self, ctx, tag_ID: int):
        """Shows the unrendered text content of a tag"""
        record = await self.bot.db.fetchrow('''
            UPDATE tags
            SET views = views + 1
            WHERE id = $1
                AND server_id = $2
            RETURNING *;
            ''', tag_ID, ctx.guild.id)
        await self.send_tag_contents(ctx, record, send_raw=True)


    @tag_id.command(name='alias')
    async def create_tag_alias_by_id(self, ctx, tag_ID: int, *, new_alias: str):
        """Creates another name for an existing tag"""
        await self.check_tag_ownership_permission(ctx, ctx.author)
        await self.validate_new_tag_info(new_alias, server_id=ctx.guild.id)

        record = await self.bot.db.fetchrow('''
            SELECT *
            FROM tags
            WHERE id = $1
                AND server_id = $2;
            ''', tag_ID, ctx.guild.id)

        await self.handle_tag_alias_creation(ctx, record, new_alias)


    @tag_id.command(name='stats', hidden=True)
    async def tag_stats_by_id(self, ctx, tag_ID: int):
        """Shows tag statistics about a member or the server"""
        # TODO
        await ctx.send('This command is under construction.')


    async def send_tag_contents(self, ctx, record: asyncpg.Record, send_raw: bool = False) -> None:
        """Sends ctx the contents of a tag or an error message if necessary
        
        If record is an alias, the parent record will be retrieved.
        """
        if record is None:
            raise commands.BadArgument('Tag not found.')
        
        if record['parent_tag_id']:
            record = await self.bot.db.fetchrow('''
                SELECT *
                FROM tags
                WHERE id = $1;
                ''', record['parent_tag_id'])

        if send_raw:
            content = record['content'].replace('`', '\`')
            if record['file_url']:
                content += '\n' + record['file_url']
            await ctx.send(content)
        elif record['file_url'] is None:
            await ctx.send(record['content'])
        else:
            await self.handle_attachment_sending(ctx, record)


    async def handle_attachment_sending(self, ctx, record: asyncpg.Record) -> None:
        """Gets and sends to ctx a tag's attachment, as well as any content it may have
        
        An attachment is required, but text content is optional.
        Assumes record['file_url'] is not None. Sends ctx an error message if necessary.
        """
        file_bytes = await self.get_attachment_bytes(ctx, record)
        if file_bytes:
            with io.BytesIO(file_bytes) as binary_stream:
                file_name = record['file_url'].split('.')[-2]
                file_type = record['file_url'].split('.')[-1]
                file = discord.File(binary_stream, f'{file_name}.{file_type}')
                await ctx.send(record['content'], file=file)
        else:
            await ctx.send('This tag may contain a type of attachment that is not compatible with Discord bots.\n')
            await ctx.send(record['content'])


    async def get_attachment_bytes(self, ctx, record: asyncpg.Record) -> Optional[bytes]:
        """Gets the bytes of the tag's attachment with an async GET request

        Assumes record['file_url'] is not None. Sends ctx an error message and returns None if the request fails.
        """
        async with self.bot.session.get(record['file_url']) as response:
            if not response.ok:
                await ctx.send("This tag's attachment cannot be accessed for some reason. The message that created the tag may have been deleted.")
                return None
            else:
                file_bytes = await response.read()
                return file_bytes


    async def send_tag_info(self, ctx, record: asyncpg.Record) -> None:
        """Sends ctx the info of a tag or an error message if necessary"""
        if record is None:
            raise commands.BadArgument('Tag not found.')

        owner = ctx.guild.get_member(record['owner_id'])
        if owner is not None:
            owner = owner.name + '#' + owner.discriminator
        else:
            owner = record['owner_id']

        if record['parent_tag_id']:
            parent_tag = f'This tag is an alias to\nthe tag with ID {record["parent_tag_id"]}.\n'

        embed = discord.Embed()
        timestamp = await create_relative_timestamp(record['created'])
        embed.add_field(name=record['name'],
            value=f'owner: {owner}\n'
                + f'created: {timestamp}\n'
                + f'views: {record["views"]}\n'
                + f'ID: {record["id"]}\n'
                + parent_tag)

        await ctx.send(embed=embed)


    async def paginate_tag_list(self, ctx, title: str, records: List[asyncpg.Record]) -> None:
        """Sends ctx a list of tag names, paginated and with reaction buttons"""
        records = sorted(records, key=lambda x: x['name'])
        entries = []
        for i, r in enumerate(records):
            tag_name = r['name'].replace('`', '\`')
            entries.append(f'{i+1}. `{tag_name}` (ID: {r["id"]})')

        paginator = MyPaginator(title=title, embed=True, timeout=90, use_defaults=True, entries=entries, length=15)

        await paginator.start(ctx)


    async def check_tag_ownership_permission(self, ctx, member: discord.Member) -> bool:
        """Raises commands.UserInputError if the author has >= the maximum number of tags allowed
        
        Does NOT check whether they own the tag.
        """
        if member.bot:
            raise commands.UserInputError('Bots cannot own tags.')
        members_tag_count = await self.count_members_tags(ctx.author.id)
        if members_tag_count >= self.tag_ownership_limit \
                and self.bot.owner_id != ctx.author.id:
            raise commands.UserInputError(f'The current limit to how many tags each person can have is {self.tag_ownership_limit}.')

        return True


    async def count_members_tags(self, member_id: int) -> int:
        """Counts how many tags a member has globally"""
        records = await self.bot.db.fetch('''
            SELECT *
            FROM tags
            WHERE owner_id = $1;
            ''', member_id)
        if records:
            return len(records)
        return 0


    async def validate_new_tag_info(self, name: str = None, content: str = None, server_id: int = None) -> bool:
        """Validates the name and content of a new tag

        Raises commands.BadArgument if
        * the name or content are too long or too short,
        * the name starts with a tag subcommand name,
        * or the name is the same as an existing tag name (not case-sensitive).

        If any of the args are None, not all of the new tag validation will be completed.
        The server_id arg is needed to validate a new tag name.
        """
        # Prevent new tag names from starting with tag subcommand names.
        tag_subcommands: List[str] = []
        tag_command = self.bot.get_command('tag')
        for c in tag_command.commands:
            tag_subcommands.append(c.name)
            tag_subcommands.extend(c.aliases)
        if name.split()[0] in tag_subcommands:
            raise commands.BadArgument(f'Tag names must not begin with a tag subcommand.')

        # Prevent new tag names from being the same as existing tag names; not case-sensitive.
        records = await self.bot.db.fetch('''
            SELECT *
            FROM tags
            WHERE LOWER(name) = LOWER($1)
                AND server_id = $2;
            ''', name, server_id)
        if records and len(records):
            raise commands.BadArgument(f'A tag named "{name}" already exists.')

        # Validate the name and content length.
        if name is not None:
            if len(name) > self.tag_name_length_limit:
                raise commands.BadArgument(f'Tag name length must be {self.tag_name_length_limit} characters or fewer.')
            if len(name) == 0:
                raise commands.BadArgument(f'Tag name length must be at least 1 character.')
        if content is not None:
            if len(content) > self.tag_content_length_limit:
                raise commands.BadArgument(f'Tag content length must be {self.tag_content_length_limit} characters or fewer.')
            if len(content) == 0:
                raise commands.BadArgument(f'Tag content length must be at least 1 character.')

        return True


    async def handle_tag_cleanup(self, ctx, record: asyncpg.Record) -> None:
        """Deletes any aliases if and only if record is not an alias, and sends ctx a status update

        Assumes the tag in record was just deleted, or that record is None because the tag wasn't found.
        """
        if record is None:
            raise commands.BadArgument('Tag not found.')

        tag_name = record['name']
        if record['parent_tag_id']:
            await ctx.send(f'Successfully deleted alias "{tag_name}".')
        else:
            n_deleted = await self.delete_tag_aliases(ctx, tag_name, record['id'])
            if n_deleted:
                await ctx.send(f'Successfully deleted tag "{tag_name}" and {plural(n_deleted, "alias||es")}.')
            else:
                await ctx.send(f'Successfully deleted tag "{tag_name}".')


    async def delete_tag_aliases(self, ctx, tag_name: str, tag_ID: int) -> int:
        """Deletes any aliases if and only if tag_name is not an alias
        
        Returns the number of aliases deleted.
        """
        ret = await self.bot.db.execute('''
            DELETE FROM tags
            WHERE parent_tag_id = $1;
            ''', tag_ID)
        n_deleted = int(ret.replace('DELETE ', ''))
        return n_deleted


    async def handle_tag_transfer(self, ctx, record: asyncpg.Record, new_owner: discord.Member) -> None:
        """Transfers ownership of a tag and all its aliases, and sends ctx a status update

        If record is an alias, the parent tag and all its aliases will still be transferred.
        Assumes ctx.author has permission to transfer the tag and new_owner has permission to receive the tag.
        Assumes the tag was not found if record is None.
        """
        if record is None:
            raise commands.BadArgument('Tag not found.')

        tag_name = record['name']
        owner_name = f'{new_owner.name}#{new_owner.discriminator}'
        n_transferred = await self.transfer_tag_ownership(ctx, record, new_owner)
        if n_transferred:
            await ctx.reply(f'Tag "{tag_name}" and its {n_transferred-1} aliases now belong to {owner_name}!')
        else:
            await ctx.reply(f'Tag "{tag_name}" now belongs to {owner_name}!')


    async def transfer_tag_ownership(self, ctx, record: asyncpg.Record, new_owner: discord.Member) -> int:
        """Transfers ownership of a tag and all its aliases, and returns the number transferred

        If record is an alias, the parent tag and all its aliases will still be transferred.
        Assumes ctx.author has permission to transfer the tag and new_owner has permission to receive the tag.
        """
        if record['parent_tag_id'] is None:
            parent_tag_id = record['id']
        else:
            parent_tag_id = record['parent_tag_id']
        ret = await self.bot.db.execute('''
            UPDATE tags
            SET owner_id = $1
            WHERE id = $2
                OR parent_tag_id = $2;
            ''', new_owner.id, parent_tag_id)

        n_transferred = int(ret.replace('UPDATE ', ''))
        return n_transferred


    async def handle_tag_edit(self, ctx, record: asyncpg.Record, new_content: str) -> None:
        """Edits a tag's content and/or attachment URL, and sends ctx a status update
        
        Any attachment URL is automatically retrieved from ctx.
        """
        file_url = await get_attachment_url(ctx)
        await self.bot.db.execute('''
            UPDATE tags
            SET content = $1,
                file_url = $2
            WHERE id = $3;
            ''', new_content, file_url, record['id'])

        tag_name = record['name']
        await ctx.send(f'Successfully edited tag "{tag_name}"')


    async def handle_tag_alias_creation(self, ctx, record: asyncpg.Record, new_alias: str) -> None:
        """Validates alias creation options, creates the alias, and sends ctx a status update
        
        Assumes the tag was not found if record is None.
        """
        if record is None:
            raise commands.BadArgument('Tag not found.')
        if record['owner_id'] != ctx.author.id:
            raise commands.BadArgument('You cannot create an alias for a tag that does not belong to you.')
        if record['parent_tag_id'] is not None:
            raise commands.BadArgument('You cannot create an alias for an alias.')

        now = datetime.now(timezone.utc)
        try:
            await self.bot.db.execute('''
                INSERT INTO tags
                (name, parent_tag_id, created, owner_id, server_id)
                VALUES ($1, $2, $3, $4, $5);
                ''', new_alias, record['parent_tag_id'], now, ctx.author.id, ctx.guild.id)
            
            await ctx.send(f'Successfully created tag alias "{new_alias}"')
        except asyncpg.exceptions.UniqueViolationError:
            raise commands.BadArgument(f'A tag named "{new_alias}" already exists.')


def setup(bot):
    bot.add_cog(Tags(bot))
