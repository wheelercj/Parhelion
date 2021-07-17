# external imports
import discord
from discord.ext import commands, buttons
import asyncpg
import io
from typing import Optional, List

# internal imports
from common import split_input, get_attachment_url, format_timestamp


'''
    CREATE TABLE IF NOT EXISTS tags (
        id SERIAL PRIMARY KEY,
        name VARCHAR(50) NOT NULL,
        content VARCHAR(1500) NOT NULL,
        file_url TEXT,
        created TIMESTAMP NOT NULL,
        owner_id BIGINT NOT NULL,
        server_id BIGINT NOT NULL,
        views INT DEFAULT 0,
        UNIQUE (name, server_id)
    )
'''


class Paginator(buttons.Paginator):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class Tags(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    async def cog_check(self, ctx):
        if not ctx.guild:
            raise commands.NoPrivateMessage
        return True


    @commands.group(invoke_without_command=True)
    async def tag(self, ctx, *, tag_name: str):
        """Finds and shows a tag's contents
        
        You can use tags to quickly save and share messages, such as for FAQs. Tags can be viewed by anyone on the server, but not other servers.
        """
        view_tag_command = self.bot.get_command('tag view')
        await ctx.invoke(view_tag_command, tag_name=tag_name)


    @tag.command(name='view')
    async def view_tag(self, ctx, *, tag_name: str):
        """An alias for `tag` in case a tag name conflicts with a subcommand"""
        record = await self.bot.db.fetchrow('''
            UPDATE tags
            SET views = views + 1
            WHERE name = $1
                AND server_id = $2
            RETURNING *;
            ''', tag_name, ctx.guild.id)
        
        await self.send_tag(ctx, record)


    @tag.command(name='create', aliases=['c'])
    async def create_tag(self, ctx, *, name_and_content: str):
        """Creates a new tag

        If the tag name has spaces, surround it with double quotes. If the tag has an attachment, the message in which the tag was created must not be deleted, or the attachment will be lost.
        """
        if await self.count_members_tags(ctx.author) >= 15:
            await ctx.send('The current limit to how many tags each person can have is 15. This will increase in the future.')
            return

        try:
            name, content = await split_input(name_and_content)
            now = ctx.message.created_at
            file_url = await get_attachment_url(ctx)

            ret = await self.bot.db.execute('''
                INSERT INTO tags
                (name, content, file_url, created, owner_id, server_id)
                VALUES ($1, $2, $3, $4, $5, $6)
                ''', name, content, file_url, now, ctx.author.id, ctx.guild.id)

            if ret == 'INSERT 0':
                await ctx.send('Error. Unable to create tag.')
                return
        except asyncpg.exceptions.UniqueViolationError:
            await ctx.send(f'A tag named "{name}" already exists.')
        except Exception as e:
            await ctx.send(f'Error: {e}')
        else:
            await ctx.send(f'Successfully created tag "{name}"')


    @tag.command(name='list')
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
            await ctx.send(f'{member.name}#{member.discriminator} has no tags on this server.')
            return

        title = f"{member.name}#{member.discriminator}'s tags"
        await self.paginate_tag_list(ctx, title, records)


    @commands.command(hidden=True)
    async def tags(self, ctx, member: discord.Member = None):
        """Lists the names of yours or someone else's tags on this server; this is an alias for `tag list`"""
        tag_list_command = self.bot.get_command('tag list')
        await ctx.invoke(tag_list_command, member=member)


    @tag.command(name='info')
    async def tag_info(self, ctx, *, tag_name: str):
        """Shows info about a tag"""
        record = await self.bot.db.fetchrow('''
            SELECT *
            FROM tags
            WHERE name = $1
                AND server_id = $2;
            ''', tag_name, ctx.guild.id)

        if record is None:
            await ctx.send('Tag not found.')
            return

        owner = ctx.guild.get_member(record['owner_id'])
        if owner is not None:
            owner = owner.name + '#' + owner.discriminator
        else:
            owner = record['owner_id']

        created = await format_timestamp(record["created"])

        embed = discord.Embed()
        embed.add_field(name=record['name'],
            value=f'owner: {owner}\n'
                + f'created: {created}\n'
                + f'views: {record["views"]}\n'
                + f'ID: {record["id"]}')

        await ctx.send(embed=embed)


    @tag.command(name='edit')
    async def edit_tag(self, ctx, *, name_and_content: str):
        """Rewrites one of your tags

        If the tag has an attachment, the message in which the tag was edited must not be deleted, or the attachment will be lost.
        """
        name, content = await split_input(name_and_content)
        file_url = await get_attachment_url(ctx)

        returned_tag_name = await self.bot.db.fetchval('''
            UPDATE tags
            SET content = $1,
                file_url = $2
            WHERE name = $3
                AND owner_id = $4
                AND server_id = $5
            RETURNING name;
            ''', content, file_url, name, ctx.author.id, ctx.guild.id)

        if returned_tag_name is None:
            await ctx.send('Tag not found.')
        else:
            await ctx.send(f'Successfully edited tag "{name}"')


    @tag.command(name='delete', aliases=['del'])
    async def delete_tag(self, ctx, *, tag_name: str):
        """Deletes one of your tags"""
        returned_tag_name = await self.bot.db.fetchval('''
            DELETE FROM tags
            WHERE name = $1
                AND owner_id = $2
                AND server_id = $3
            RETURNING name;
            ''', tag_name, ctx.author.id, ctx.guild.id)

        if returned_tag_name is None:
            await ctx.send('Tag not found.')
        else:
            await ctx.send(f'Successfully deleted tag "{tag_name}"')


    @tag.command(name='mod-delete', aliases=['mdel', 'moddelete'])
    @commands.has_guild_permissions(manage_messages=True)
    async def mod_delete_tag(self, ctx, *, tag_name: str):
        """Deletes one of anyone's tags"""
        returned_tag_name = await self.bot.db.fetchval('''
            DELETE FROM tags
            WHERE name = $1
                AND server_id = $2
            RETURNING name;
            ''', tag_name, ctx.guild.id)
        
        if returned_tag_name is None:
            await ctx.send('Tag not found.')
        else:
            await ctx.send(f'Successfully deleted tag "{tag_name}"')


    @tag.command(name='claim')
    async def claim_tag(self, ctx, *, tag_name: str):
        """Gives you ownership of a tag if its owner left the server"""
        if await self.count_members_tags(ctx.author) >= 15:
            await ctx.send('The current limit to how many tags each person can have is 15. This will increase in the future.')
            return

        owner_id = await self.get_tag_owner_id_by_name(ctx, tag_name)
        if owner_id is None:
            await ctx.send('Tag not found.')
            return
        if owner_id == ctx.author.id:
            await ctx.send('This tag already belongs to you.')
            return

        owner = ctx.guild.get_member(owner_id)
        if owner is not None:
            await ctx.send("The tag's owner is still in this server.")
            return

        returned_tag_name = await self.bot.db.fetchval('''
            UPDATE tags
            SET owner_id = $1
            WHERE name = $2
                AND server_id = $3
            RETURNING name;
            ''', ctx.author.id, tag_name, ctx.guild.id)

        if returned_tag_name is None:
            await ctx.send(f'Error. Unable to claim tag.')
        else:
            await ctx.reply(f'Tag "{tag_name}" now belongs to you!')


    @tag.command(name='transfer')
    async def transfer_tag(self, ctx, member: discord.Member, *, tag_name: str):
        """Gives a server member ownership of one of your tags"""
        if await self.count_members_tags(member) >= 15:
            await ctx.send('The current limit to how many tags each person can have is 15. This will increase in the future.')
            return

        tag_name = await self.bot.db.fetchval('''
            UPDATE tags
            SET owner_id = $1
            WHERE owner_id = $2
                AND name = $3
                AND server_id = $4
            RETURNING name;
            ''', member.id, ctx.author.id, tag_name, ctx.guild.id)

        if tag_name is None:
            await ctx.send(f'Tag not found.')
        else:
            await ctx.send(f'Tag "{tag_name}" now belongs to {member.name}#{member.discriminator}!')


    @tag.command(name='raw')
    async def get_raw_tag(self, ctx, *, tag_name: str):
        """Shows the unrendered text content of a tag"""
        record = await self.bot.db.fetchrow('''
            UPDATE tags
            SET views = views + 1
            WHERE name = $1
                AND server_id = $2
            RETURNING *;
            ''', tag_name, ctx.guild.id)

        if record is None:
            await ctx.send('Tag not found.')
        else:
            content = record['content'].replace('`', '\`')
            await ctx.send(content)


    @tag.command(name='search', hidden=True)
    async def tag_search(self, ctx):
        """Searches for a tag"""
        await ctx.send('This command is under construction.')


    @tag.command(name='all')
    async def list_all_tags(self, ctx):
        """Lists all tags on this server"""
        records = await self.bot.db.fetch('''
            SELECT *
            FROM tags
            WHERE server_id = $1;
            ''', ctx.guild.id)

        if not records or not len(records):
            await ctx.send(f'There are no tags on this server.')
            return

        title = ''
        await self.paginate_tag_list(ctx, title, records)

    
    @tag.command(name='alias', hidden=True)
    async def create_tag_alias(self, ctx):
        """Creates another name for an existing tag"""
        await ctx.send('This command is under construction.')


    @tag.command(name='stats', hidden=True)
    async def tag_stats(self, ctx):
        """Shows tag statistics about a member or the server"""
        await ctx.send('This command is under construction.')


    @tag.command(name='make', hidden=True)
    async def make_tag(self, ctx):
        """Interactively helps you create a tag"""
        await ctx.send('This command is under construction.')


################
# tag_ID group #
################


    @tag.group(name='id')
    async def tag_id(self, ctx, tag_ID: int = None):
        """A group of commands using tag IDs instead of tag names"""
        view_tag_by_id_command = self.bot.get_command('tag id view')
        await ctx.invoke(view_tag_by_id_command, tag_ID=tag_ID)


    @tag_id.command(name='view')
    async def view_tag_by_id(self, ctx, tag_ID: int = None):
        """An alias for `tag id` in case a tag ID conflicts with a subcommand"""
        if tag_ID is None:
            await ctx.send_help('tag id')
        else:
            record = await self.bot.db.fetchrow('''
                UPDATE tags
                SET views = views + 1
                WHERE id = $1
                    AND server_id = $2
                RETURNING *;
                ''', tag_ID, ctx.guild.id)

            await self.send_tag(ctx, record)


    @tag_id.command(name='delete', aliases=['del'])
    async def delete_tag_by_id(self, ctx, tag_ID: int):
        """Deletes one of your tags"""
        returned_tag_name = await self.bot.db.fetchval('''
            DELETE FROM tags
            WHERE id = $1
                AND owner_id = $2
                AND server_id = $3
            RETURNING name;
            ''', tag_ID, ctx.author.id, ctx.guild.id)

        if returned_tag_name is None:
            await ctx.send('Tag not found.')
        else:
            await ctx.send(f'Successfully deleted tag "{returned_tag_name}"')


    @tag_id.command(name='mod-delete', aliases=['mdel', 'moddelete'])
    @commands.has_guild_permissions(manage_messages=True)
    async def mod_delete_tag_by_id(self, ctx, tag_ID: int):
        """Deletes one of anyone's tags"""
        returned_tag_name = await self.bot.db.fetchval('''
            DELETE FROM tags
            WHERE id = $1
                AND server_id = $2
            RETURNING name;
            ''', tag_ID, ctx.guild.id)

        if returned_tag_name is None:
            await ctx.send('Tag not found.')
        else:
            await ctx.send(f'Successfully deleted tag "{returned_tag_name}"')


    @tag_id.command(name='claim')
    async def claim_tag_by_id(self, ctx, tag_ID: int):
        """Gives you ownership of a tag if its owner left the server"""
        if await self.count_members_tags(ctx.author) >= 15:
            await ctx.send('The current limit to how many tags each person can have is 15. This will increase in the future.')
            return

        owner_id = await self.get_tag_owner_id_by_id(ctx, tag_ID)
        if owner_id is None:
            await ctx.send('Tag not found.')
            return
        if owner_id == ctx.author.id:
            await ctx.send('This tag already belongs to you.')
            return

        owner = ctx.guild.get_member(owner_id)
        if owner is not None:
            await ctx.send("The tag's owner is still in this server.")
            return

        returned_tag_name = await self.bot.db.fetchval('''
            UPDATE tags
            SET owner_id = $1
            WHERE id = $2
                AND server_id = $3
            RETURNING name;
            ''', ctx.author.id, tag_ID, ctx.guild.id)

        if returned_tag_name is None:
            await ctx.send(f'Error. Unable to claim tag.')
        else:
            await ctx.reply(f'Tag "{returned_tag_name}" now belongs to you!')


    @tag_id.command(name='info', hidden=True)
    async def tag_info_by_id(self, ctx, tag_ID: int):
        """Shows info about a tag"""
        await ctx.send('This command is under construction.')


    @tag_id.command(name='edit', hidden=True)
    async def edit_tag_by_id(self, ctx, tag_ID: int):
        """Rewrites one of your tags

        If the tag has an attachment, the message in which the tag was edited must not be deleted, or the attachment will be lost.
        """
        await ctx.send('This command is under construction.')


    @tag_id.command(name='transfer', hidden=True)
    async def transfer_tag_by_id(self, ctx, tag_ID: int):
        """Gives a server member ownership of one of your tags"""
        await ctx.send('This command is under construction.')


    @tag_id.command(name='raw', hidden=True)
    async def get_raw_tag_by_id(self, ctx, tag_ID: int):
        """Shows the unrendered text content of a tag"""
        await ctx.send('This command is under construction.')


    @tag_id.command(name='alias', hidden=True)
    async def create_tag_alias_by_id(self, ctx, tag_ID: int):
        """Creates another name for an existing tag"""
        await ctx.send('This command is under construction.')


    @tag_id.command(name='stats', hidden=True)
    async def tag_stats_by_id(self, ctx, tag_ID: int):
        """Shows tag statistics about a member or the server"""
        await ctx.send('This command is under construction.')


    async def send_tag(self, ctx, record: asyncpg.Record) -> None:
        """Sends ctx the contents of a tag or an error message if necessary"""
        if record is None:
            await ctx.send('Tag not found.')
        elif record['file_url'] is None:
            await ctx.send(record['content'])
        else:
            try:
                async with self.bot.session.get(record['file_url']) as response:
                    if not response.ok:
                        await ctx.send(record['content'])
                        await ctx.send("This tag's attachment cannot be accessed for some reason. The message that created the tag may have been deleted.")
                    else:
                        image_bytes = await response.read()
                with io.BytesIO(image_bytes) as binary_stream:
                    file_name = record['file_url'].split('.')[-2]
                    file_type = record['file_url'].split('.')[-1]
                    file = discord.File(binary_stream, f'{file_name}.{file_type}')
                    await ctx.send(record['content'], file=file)
            except discord.errors.HTTPException as e:
                if 'empty message' in e.text:
                    await ctx.send("This tag is empty. It may contain a type of attachment that Discord doesn't provide working URLs to.")


    async def paginate_tag_list(self, ctx, title: str, records: List[asyncpg.Record]) -> None:
        """Sends ctx a list of tag names, paginated and with reaction buttons"""
        records = sorted(records, key=lambda x: x['name'])
        entries = []
        for i, r in enumerate(records):
            tag_name = r['name'].replace('`', '\`')
            entries.append(f'{i+1}. `{tag_name}` (ID: {r["id"]})')

        paginator = Paginator(title=title, embed=True, timeout=90, use_defaults=True, entries=entries, length=15)

        await paginator.start(ctx)


    async def count_members_tags(self, member: discord.Member) -> int:
        """Counts how many tags a member has globally"""
        records = await self.bot.db.fetch('''
            SELECT *
            FROM tags
            WHERE owner_id = $1;
            ''', member.id)

        if records:
            return len(records)
        return 0


    async def get_tag_owner_id_by_name(self, ctx, tag_name: str) -> Optional[int]:
        """Gets the user ID of a tag's owner

        Returns None if the tag does not exist at ctx.guild.
        """
        owner_id = await self.bot.db.fetchval('''
            SELECT owner_id
            FROM tags
            WHERE name = $1
                AND server_id = $2;
        ''', tag_name, ctx.guild.id)
        
        return owner_id


    async def get_tag_owner_id_by_id(self, ctx, tag_ID: int) -> Optional[int]:
        """Gets the user ID of a tag's owner

        Returns None if the tag does not exist at ctx.guild.
        """
        owner_id = await self.bot.db.fetchval('''
            SELECT owner_id
            FROM tags
            WHERE id = $1
                AND server_id = $2;
        ''', tag_ID, ctx.guild.id)
        
        return owner_id


def setup(bot):
    bot.add_cog(Tags(bot))
