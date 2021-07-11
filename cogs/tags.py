# external imports
import discord
from discord.ext import commands
from datetime import datetime
import asyncpg

# internal imports
from common import split_input


'''
    CREATE TABLE IF NOT EXISTS tags (
        name VARCHAR(30) NOT NULL,
        content VARCHAR(1500) NOT NULL,
        creation_date TIMESTAMP NOT NULL,
        author_id BIGINT NOT NULL,
        server_id BIGINT NOT NULL,
        PRIMARY KEY (name, server_id)
    )
'''


class Tags(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    async def cog_check(self, ctx):
        if not ctx.guild:
            raise commands.NoPrivateMessage
        return True


    @commands.group(invoke_without_command=True)
    async def tag(self, ctx, *, name: str):
        """Finds and shows a tag
        
        You can use tags to quickly save and share messages, such as for FAQs. Tags can be viewed by anyone on the server, but not other servers.
        """
        content = await self.bot.db.fetchval('''
            SELECT content
            FROM tags
            WHERE name = $1
                AND server_id = $2;
            ''', name, ctx.guild.id)

        if content is None:
            await ctx.send('Tag not found.')
        else:
            await ctx.send(content)


    @tag.command(name='create')
    async def create_tag(self, ctx, *, content: str):
        """Creates a new tag
        
        If the tag name has spaces, surround it with double quotes.
        The maximum tag name length is 30 characters, and the maximum tag
        body length is 1500 characters. Currently, images are not supported.
        """
        name, content = await split_input(content)
        now = datetime.now()

        if not len(content):
            await ctx.send('Cannot create an empty tag.')
            return
        if await self.count_authors_tags(ctx) >= 15:
            await ctx.send('The current limit to how many tags each person can have is 15. This will increase in the future.')
            return

        try:
            await self.bot.db.execute('''
                INSERT INTO tags
                (name, content, creation_date, author_id, server_id)
                VALUES ($1, $2, $3, $4, $5)
                ''', name, content, now, ctx.author.id, ctx.guild.id)
        except asyncpg.exceptions.UniqueViolationError:
            await ctx.send(f'A tag named "{name}" already exists.')
        else:
            await ctx.send(f'Successfully created tag "{name}"')


    @tag.command(name='list')
    async def list_tags(self, ctx):
        """Lists the names of your tags"""
        records = await self.bot.db.fetch('''
            SELECT *
            FROM tags
            WHERE author_id = $1
                AND server_id = $2;
            ''', ctx.author.id, ctx.guild.id)

        if not len(records):
            await ctx.send('You have no tags on this server.')
            return

        output = ''
        for i, r in enumerate(records):
            output += f'{i+1}. {r["name"]}\n'
        
        embed = discord.Embed()
        embed.add_field(name=f"{ctx.author.display_name}'s tags",
            value=output)
        
        await ctx.send(embed=embed)


    @tag.command(name='info')
    async def tag_info(self, ctx, *, name: str):
        """Shows info about a tag"""
        record = await self.bot.db.fetchrow('''
            SELECT *
            FROM tags
            WHERE name = $1
                AND server_id = $2;
            ''', name, ctx.guild.id)

        if record is None:
            await ctx.send('Tag not found.')
            return

        author = ctx.guild.get_member(record['author_id'])
        if author is not None:
            author = author.display_name
        else:
            author = record['author_id']

        embed = discord.Embed()
        embed.add_field(name=record['name'],
            value=f'author: {author}\n'
                + f'created on {record["creation_date"]}')

        await ctx.send(embed=embed)


    @tag.command(name='edit')
    async def edit_tag(self, ctx, *, content: str):
        """Rewrites one of your tags
        
        The maximum tag length is 1500 characters. Currently, images are
        not supported.
        """
        name, content = await split_input(content)        

        if not await self.authors_tag_exists(ctx, name):
            return

        await self.bot.db.execute('''
            UPDATE tags
            SET content = $1
            WHERE name = $2
                AND server_id = $3;
            ''', content, name, ctx.guild.id)
        
        await ctx.send(f'Successfully edited tag "{name}"')


    @tag.command(name='delete')
    async def delete_tag(self, ctx, *, name: str):
        """Deletes one of your tags"""
        if not await self.authors_tag_exists(ctx, name):
            return

        await self.bot.db.execute('''
            DELETE FROM tags
            WHERE name = $1
                AND server_id = $2;
            ''', name, ctx.guild.id)

        await ctx.send(f'Successfully deleted tag "{name}"')


    @tag.command(name='claim')
    async def claim_tag(self, ctx, *, name: str):
        """Gives you ownership of a tag if its owner left the server"""
        if await self.count_authors_tags(ctx) >= 15:
            await ctx.send('The current limit to how many tags each person can have is 15. This will increase in the future.')
            return

        author_id = await self.get_tag_author(ctx, name)
        member = ctx.guild.get_member(author_id)
        
        if author_id == ctx.author.id:
            await ctx.send('This tag already belongs to you.')
            return
        if member is not None:
            await ctx.send("The tag's owner is still in this server.")
            return

        await self.bot.db.execute('''
            UPDATE tags
            SET author_id = $1
            WHERE name = $2
                AND server_id = $3;
            ''', ctx.author.id, name, ctx.guild.id)

        await ctx.reply(f'Tag "{name}" now belongs to you!')


    async def count_authors_tags(self, ctx) -> int:
        """Counts how many tags ctx.author has globally"""
        records = await self.bot.db.fetch('''
            SELECT *
            FROM tags
            WHERE author_id = $1;
            ''', ctx.author.id)

        return len(records)


    async def get_tag_author(self, ctx, tag_name: str) -> int:
        """Gets the ID of a tag's author
        
        Returns None if the tag does not exist at ctx.guild.
        """
        author_id = await self.bot.db.fetchval('''
            SELECT author_id
            FROM tags
            WHERE name = $1
                AND server_id = $2;
        ''', tag_name, ctx.guild.id)
        
        return author_id


    async def authors_tag_exists(self, ctx, tag_name: str) -> bool:
        """Confirms whether a tag exists at ctx.guild and belongs to ctx.author
        
        Sends ctx an error message if False will be returned.
        """
        author_id = await self.get_tag_author(ctx, tag_name)

        if author_id is None:
            await ctx.send('Tag not found.')
            return False
        if author_id != ctx.author.id:
            await ctx.send('This tag does not belong to you.')
            return False

        return True


def setup(bot):
    bot.add_cog(Tags(bot))
