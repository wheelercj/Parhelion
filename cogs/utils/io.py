import os
import traceback
from urllib.parse import quote_plus

import discord  # https://pypi.org/project/discord.py/
from discord.ext import commands  # https://pypi.org/project/discord.py/


#########
# input #
#########


class LinkButton(discord.ui.View):
    """A button that opens a website when pressed"""

    def __init__(self, label: str, url: str, query: str = "") -> None:
        """Creates a link button

        Example uses:
        await ctx.send(view=LinkButton("click here", "zombo.com"))
        await ctx.send(view=LinkButton("search", "google.com/search?q=", user_input))

        Parameters
        ----------
        label: str
            The text that appears on the button.
        url: str
            The URL to the website to open when the button is pressed.
        query: str
            Text to append to the URL that may have characters that need to be escaped.
        """
        super().__init__()
        if "://" not in url:
            url = f"https://{url}"
        if query:
            url = f"{url}{quote_plus(query)}"
        self.add_item(discord.ui.Button(label=label, url=url))


async def unwrap_code_block(statement: str) -> tuple[str, str, str]:
    """Removes triple backticks and a syntax name around a code block

    Returns any syntax name found, the unwrapped code, and anything after closing
    triple backticks. Any syntax name must be on the same line as the leading triple
    backticks, and code must be on the next line(s). If there are not triple backticks,
    the returns are 'txt' and the unchanged input. If there are triple backticks and no
    syntax is specified, the first two returns will be 'txt' and the unwrapped code
    block. If there is nothing after the closing triple backticks, the third returned
    value will be an empty string. The result is not dedented. Closing triple backticks
    are optional (unless something is needed after them).
    """
    syntax = "txt"
    if not statement.startswith("```"):
        return syntax, statement, ""
    statement = statement[3:]
    syntax, statement = await find_codeblock_syntax_name(syntax, statement)
    suffix = ""
    if "```" in statement:
        statement, suffix = statement.split("```", 1)
    if statement.endswith("\n"):
        statement = statement[:-1]
    return syntax, statement, suffix


async def find_codeblock_syntax_name(syntax: str, statement: str) -> tuple[str, str]:
    """Finds the syntax name if one is given

    Returns the syntax name and the rest of the code block.
    """
    i = statement.find("\n")
    if i != -1:
        first_line = statement[:i].strip()
        if len(first_line):
            syntax = first_line
            statement = statement[i:]
    if statement.startswith("\n"):
        statement = statement[1:]
    return syntax, statement


async def split_input(message: str) -> tuple[str, str]:
    """Splits a string into two strings

    If the input string begins with double quotes and has another double quotes later,
    the contents of those double quotes will be the first string returned. Otherwise,
    the first string returned will be the first word of the input string. The second
    string returned will be what remains of the input string.
    """
    name = None
    if message.startswith('"'):
        i = message.find('"', 2)
        if i != -1:
            name = message[1:i]
            content = message[i + 1 :].strip()
    if name is None:
        name = message.split()[0]
        content = " ".join(message.split()[1:])
    return name, content


async def get_attachment_url(ctx) -> str | None:
    """Gets the proxy URL of an attachment if there is one

    Attempts to filter out invalid URLs.
    """
    if ctx.message.attachments:
        file_url = ctx.message.attachments[0].proxy_url
        file_type = file_url.split(".")[-1]
        if not await is_supported_type(file_type):
            raise ValueError(
                f"Attachment links do not work for files of type {file_type}"
            )
        return file_url
    return None


async def is_supported_type(file_type: str) -> bool:
    """Says whether the file type is supported by Discord's CDN

    This function is incomplete; more file types need to be tested.
    """
    unsupported_types = ["md", "pdf"]
    # TODO: find a complete list of supported file types and use that instead.
    return file_type not in unsupported_types


class Channel(commands.Converter):
    """Converter for most types of Discord channels

    Precedence:
        TextChannelConverter
        VoiceChannelConverter
        StageChannelConverter
        CategoryChannelConverter

    DMChannel and GroupChannel do not have converters.
    """

    async def convert(self, ctx, argument):
        converters = [
            commands.TextChannelConverter,
            commands.VoiceChannelConverter,
            commands.StageChannelConverter,
            commands.CategoryChannelConverter,
        ]
        for converter in converters:
            try:
                channel = await converter().convert(ctx, argument)
                return channel
            except commands.ChannelNotFound:
                pass
        raise commands.BadArgument(f'Channel "{argument}" not found.')


##########
# output #
##########


async def safe_send(
    ctx, message: str, protect_postgres_host: bool = False, ephemeral: bool = False
) -> None:
    """Same as ctx.send but with extra security options"""
    postgres_host: str = os.environ.get("POSTGRES_HOST", "localhost")
    if protect_postgres_host and postgres_host in message:
        message = message.replace(postgres_host, "(PostgreSQL host)")
    await ctx.send(message, ephemeral=ephemeral)


async def send_traceback(ctx, error: BaseException, ephemeral: bool = True) -> None:
    """Sends the traceback of an exception to ctx"""
    etype = type(error)
    trace = error.__traceback__
    lines = traceback.format_exception(etype, error, trace)
    traceback_text = "".join(lines)
    await ctx.send(f"```\n{traceback_text}\n```", ephemeral=ephemeral)


async def dev_mail(
    bot,
    content: str | None = None,
    *,
    file: discord.File | None = None,
    use_embed: bool = True,
    embed_title: str = "dev mail",
) -> None:
    """Sends a private message to the bot owner"""
    user = await bot.fetch_user(bot.owner_id)
    if content and use_embed:
        embed = discord.Embed(title=embed_title, description=content)
        await user.send(embed=embed, file=file)
    else:
        await user.send(content, file=file)
