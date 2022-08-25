import os
import traceback
from typing import Optional

import discord  # https://pypi.org/project/discord.py/
from discord.ext import commands  # https://pypi.org/project/discord.py/


#########
# input #
#########


async def unwrap_code_block(statement: str) -> tuple[str, str, str]:
    """Removes triple backticks and a syntax name around a code block

    Returns any syntax name found, the unwrapped code, and anything after
    closing triple backticks. Any syntax name must be on the same line as the
    leading triple backticks, and code must be on the next line(s). If there
    are not triple backticks, the returns are 'txt' and the unchanged input. If
    there are triple backticks and no syntax is specified, the first two
    returns will be 'txt' and the unwrapped code block. If there is nothing
    after the closing triple backticks, the third returned value will be an
    empty string. The result is not dedented. Closing triple backticks are
    optional (unless something is needed after them).
    """
    syntax = "txt"

    if not statement.startswith("```"):
        return syntax, statement, ""

    statement = statement[3:]

    # Find the syntax name if one is given.
    i = statement.find("\n")
    if i != -1:
        first_line = statement[:i].strip()
        if len(first_line):
            syntax = first_line
            statement = statement[i:]
    if statement.startswith("\n"):
        statement = statement[1:]

    suffix = ""
    if "```" in statement:
        statement, suffix = statement.split("```", 1)
    if statement.endswith("\n"):
        statement = statement[:-1]

    return syntax, statement, suffix


async def split_input(message: str) -> tuple[str, str]:
    """Splits a string into two strings

    If the input string begins with double quotes and has another double quotes later, the contents of those double quotes will be the first string returned. Otherwise, the first string returned will be the first word of the input string. The second string returned will be what remains of the input string.
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


async def get_attachment_url(ctx) -> Optional[str]:
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


async def is_supported_type(file_type: str) -> bool:
    """Says whether the file type is supported by Discord's CDN

    This function is incomplete; more file types need to be tested.
    """
    unsupported_types = ["md", "pdf"]
    # TODO: find a complete list of supported file types and use that instead.
    if file_type in unsupported_types:
        return False
    return True


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


async def safe_send(ctx, message: str, protect_postgres_host: bool = False) -> None:
    """Same as ctx.send but with extra security options"""
    if protect_postgres_host:
        postgres_host = os.environ["PostgreSQL_host"]
        if postgres_host in message:
            message = message.replace(postgres_host, "(PostgreSQL host)")
            await ctx.send(message)
            return

    await ctx.send(message)


async def send_traceback(ctx, error: BaseException) -> None:
    """Sends the traceback of an exception to ctx"""
    etype = type(error)
    trace = error.__traceback__
    lines = traceback.format_exception(etype, error, trace)
    traceback_text = "".join(lines)
    await ctx.send(f"```\n{traceback_text}\n```")


async def dev_mail(
    bot, message: str, use_embed: bool = True, embed_title: str = "dev mail"
) -> None:
    """Sends a private message to the bot owner"""
    user = await bot.fetch_user(bot.owner_id)
    if use_embed:
        embed = discord.Embed(title=embed_title, description=message)
        await user.send(embed=embed)
    else:
        await user.send(message)
