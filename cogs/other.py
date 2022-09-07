import asyncio
import json
import random
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from textwrap import dedent
from typing import Optional

import async_tio  # https://pypi.org/project/async-tio/
import asyncpg  # https://pypi.org/project/asyncpg/
import discord  # https://pypi.org/project/discord.py/
import mystbin  # https://pypi.org/project/mystbin.py/
from aiohttp.client_exceptions import (
    ContentTypeError,
)  # https://pypi.org/project/aiohttp/
from deep_translator import (
    GoogleTranslator,
)  # https://pypi.org/project/deep-translator/
from deep_translator.google_trans import (
    LanguageNotSupportedException,
)  # https://pypi.org/project/deep-translator/
from deep_translator.google_trans import (
    TranslationNotFound,
)  # https://pypi.org/project/deep-translator/
from discord.abc import Messageable  # https://pypi.org/project/discord.py/
from discord.ext import commands  # https://pypi.org/project/discord.py/
from wordhoard import Antonyms  # https://pypi.org/project/wordhoard/
from wordhoard import Definitions  # https://pypi.org/project/wordhoard/
from wordhoard import Homophones  # https://pypi.org/project/wordhoard/
from wordhoard import Hypernyms  # https://pypi.org/project/wordhoard/
from wordhoard import Hyponyms  # https://pypi.org/project/wordhoard/
from wordhoard import Synonyms  # https://pypi.org/project/wordhoard/

from cogs.utils.common import block_nsfw_channels
from cogs.utils.io import get_attachment_url
from cogs.utils.io import safe_send
from cogs.utils.io import send_traceback
from cogs.utils.io import unwrap_code_block
from cogs.utils.paginator import Paginator
from cogs.utils.time import create_short_timestamp
from cogs.utils.time import get_14_digit_datetime
from cogs.utils.time import parse_time_message


class RunningQuoteInfo:
    def __init__(self, target_time: datetime, author_id: int):
        self.target_time = target_time
        self.author_id = author_id


class MyTio(async_tio.Tio):
    async def close(_):
        pass  # prevent the bot's session from being closed


class Other(commands.Cog):
    """A variety of commands that don't fit in the other categories."""

    def __init__(self, bot):
        self.bot = bot
        self.running_quote_info: RunningQuoteInfo = None
        self.quotes_task = self.bot.loop.create_task(self.run_daily_quotes())

    def cog_unload(self):
        self.quotes_task.cancel()

    async def create_table_if_not_exists(self) -> None:
        await self.bot.db.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_quotes (
                author_id BIGINT PRIMARY KEY,
                start_time TIMESTAMPTZ NOT NULL,
                target_time TIMESTAMPTZ NOT NULL,
                is_dm BOOLEAN NOT NULL,
                server_id BIGINT,
                channel_id BIGINT
            );
            """
        )

    async def run_daily_quotes(self) -> None:
        """A task that finds the next quote time, waits for that time, and sends"""
        await self.bot.wait_until_ready()
        await self.create_table_if_not_exists()
        try:
            while not self.bot.is_closed():
                target_time, author_id, destination = await self.get_next_quote_info()
                if target_time is None:
                    self.bot.logger.debug("quote task's target_time is None")
                    self.running_quote_info = None
                    self.quotes_task.cancel()
                    return
                self.running_quote_info = RunningQuoteInfo(target_time, author_id)
                await discord.utils.sleep_until(target_time)
                try:
                    await self.send_quote(destination, author_id)
                    await self.update_quote_target_time(target_time, author_id)
                except (ContentTypeError, json.decoder.JSONDecodeError) as error:
                    self.bot.logger.error(f"quote task caught an error:\n{error}")
                    await asyncio.sleep(30)
        except (
            OSError,
            discord.ConnectionClosed,
            asyncpg.PostgresConnectionError,
            Exception,
        ) as error:
            self.bot.logger.error(f"quote task caught an error:\n{error}")
            self.quotes_task.cancel()
            await asyncio.sleep(30)
            self.quotes_task = self.bot.loop.create_task(self.run_daily_quotes())
            # Could this recursion eventually cause a stack problem?

    @commands.hybrid_command(
        aliases=["link", "url", "publish", "post", "paste", "mystbin"]
    )
    async def share(self, ctx, *, text: str = None):
        """Gives you a shareable URL to your text or attachment

        Text is posted publicly on Mystb.in and cannot be edited or deleted once posted.
        Attachments stay on Discord's servers until deleted. For text, you can use a
        code block. Not all file types work for attachments.

        Parameters
        ----------
        text: Optional[str]
            The message to permanently and publicly post on Mystb.in.
        """
        await block_nsfw_channels(ctx.channel)
        async with ctx.typing():
            file_url = await get_attachment_url(ctx)
            if file_url:
                await ctx.reply(f"Here's a link to the attachment: <{file_url}>")
            if text:
                syntax, text, _ = await unwrap_code_block(text)
                text = dedent(text)
                filename = f"{await get_14_digit_datetime()}.{syntax}"
                mystbin_client = mystbin.Client(session=self.bot.session)
                paste = await mystbin_client.create_paste(
                    filename=filename, content=text, syntax=syntax
                )
                await ctx.reply(f"New Mystb.in paste created at <{str(paste)}>")

    @commands.hybrid_command(
        name="calc", aliases=["calculate", "solve", "math", "maths"]
    )
    @commands.cooldown(25, 216, commands.BucketType.default)
    async def calculate(self, ctx, *, expression: str):
        """Evaluates a math expression

        Evaluates multiple expressions if they're on separate lines, and
        allows you to use a code block. Uses the math.js API:
        https://mathjs.org/docs/expressions/syntax.html

        Parameters
        ----------
        expression: str
            The math expression to evaluate.
        """
        # The math.js API has a 10 second duration limit per evaluation and
        # allows a maximum of 10,000 requests per day (or 25 requests per 216
        # seconds).
        try:
            _, expression, _ = await unwrap_code_block(expression)
            if "**" in expression:
                raise ValueError("This command uses ^ rather than ** for exponents.")
            raw_expressions = expression.split("\n")
            expressions = json.dumps(raw_expressions)
            expressions_json = '{\n"expr": ' + expressions + "\n}"
            async with ctx.typing():
                async with self.bot.session.post(
                    "http://api.mathjs.org/v4/",
                    data=expressions_json,
                    headers={"content-type": "application/json"},
                    timeout=10,
                ) as response:
                    if not response.ok and response.status != 400:
                        raise ValueError(
                            f"API request failed with status code {response.status}."
                        )
                    json_text = await response.json()
                    if response.status == 400:
                        raise ValueError(json_text["error"])
            result = ""
            for i, expr in enumerate(raw_expressions):
                result += "\n`" + expr + "` = `" + json_text["result"][i] + "`"
            embed = discord.Embed(description=result)
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(e)
            if await self.bot.is_owner(ctx.author):
                await send_traceback(ctx, e)

    @commands.hybrid_command(name="random", aliases=["rand"], hidden=True)
    async def rand(self, ctx, low: int = 1, high: int = 6):
        """Gives a random number

        Parameters
        ----------
        low: int
            The lowest possible number.
        high: int
            The highest possible number.
        """
        low = int(low)
        high = int(high)
        if low <= high:
            await ctx.send(f"`{str(random.randint(low, high))}` (range: {low}–{high})")
        else:
            await ctx.send(f"`{str(random.randint(high, low))}` (range: {high}–{low})")

    @commands.hybrid_command(
        name="flip-coin", aliases=["flip", "flipcoin"], hidden=True
    )
    async def flip_coin(self, ctx):
        """Flips a coin"""
        n = random.randint(1, 2)
        if n == 1:
            await ctx.send("heads")
        else:
            await ctx.send("tails")

    @commands.hybrid_command(hidden=True)
    async def choose(self, ctx, choice_count: int, choices: str):
        """Chooses randomly from multiple choices

        Parameters
        ----------
        choice_count: int
            The number of choices to make.
        choices: str
            The space-separated choices to choose from.
        """
        choices_: list[str] = choices.split(" ")
        choices_made = []
        for _ in range(0, choice_count):
            choices_made.append(random.choice(choices_))
        await ctx.send(" ".join(choices_made), ephemeral=True)

    @choose.error
    async def choose_error(self, ctx, error):
        if (
            isinstance(error, commands.errors.BadArgument)
            or isinstance(error, commands.errors.CommandInvokeError)  # noqa: W503
            or isinstance(error, commands.errors.MissingRequiredArgument)  # noqa: W503
        ):
            await ctx.send(
                "Error: the first argument must be the number of choices you want to be"
                " made. Following arguments must be the choices to choose from."
            )
        else:
            await ctx.send(error)

    @commands.hybrid_command(aliases=["rotate", "rot", "shift"], hidden=True)
    async def cipher(self, ctx, n: int, *, message: str):
        """Rotates each letter n letters through the alphabet

        Parameters
        ----------
        n: int
            The number of letters of the alphabet to rotate through.
        message: str
            The message to encipher.
        """
        message = message.lower()
        new_string = ""
        alphabet = "abcdefghijklmnopqrstuvwxyz"
        for char in message:
            index = alphabet.find(char)
            if index != -1:
                new_index = (index + n) % 26
                new_string += alphabet[new_index]
            else:
                new_string += char
        await ctx.send(new_string)

    #######################
    # _run command group #
    #######################

    @commands.hybrid_group(
        name="run", aliases=["exec", "execute"], invoke_without_command=True
    )
    async def _run(self, ctx, *, code_block: str):
        """A group of commands for running code in almost any language

        Without a subcommand, this command runs code in almost any language.

        Parameters
        ----------
        code_block: str
            The markdown-style block of code to run.
        """
        cmd = self.bot.get_command("run code")
        await ctx.invoke(cmd, code_block=code_block)

    @_run.command(aliases=["c"])
    async def code(self, ctx, *, code_block: str):
        """Runs code in almost any language

        Parameters
        ----------
        code_block: str
            The markdown-style block of code to run.
        """
        async with ctx.typing():
            code_block = code_block.replace("“", '"').replace("”", '"')
            if "```" in code_block:
                language, expression, inputs = await unwrap_code_block(code_block)
            else:
                split_pieces = code_block.split(maxsplit=1)
                if len(split_pieces) == 1:
                    raise commands.BadArgument(
                        "Error: please specify the language before the code."
                    )
                language, expression = split_pieces
                inputs = ""
            language, expression = await self.parse_exec_language(language, expression)
            async with MyTio(session=self.bot.session) as tio:
                if language not in [x.tio_name for x in await tio.get_languages()]:
                    raise commands.BadArgument(f"Invalid language: {language}")
                response = await tio.execute(
                    expression, language=language, inputs=inputs
                )
            await ctx.send(f"`{language}` output:\n{response.stdout}")

    @_run.command(name="guide", aliases=["g", "i", "h", "info", "help"])
    async def exec_guide(self, ctx):
        """Explains some of the nuances of the `run` command"""
        text = dedent(
            """
            With the `run` command, you can use a triple-backtick code block and specify
            a language on its first line. Any input after the closing triple backticks
            will be used as inputs for the program (you can hold shift while pressing
            enter to go to the next line if necessary). Many languages can automatically
            wrap your code with a main function and commonly used imports if you do not
            include them. You can use the `run jargon <language>` command to see what
            code may be automatically added in front of your input if you omit the main
            function header.

            Some language names will be changed before the code is executed:
            c → c-clang
            c++ or cpp → cpp-clang
            c# or cs → cs-csc
            f# or fs → fs-core
            java → java-openjdk
            js or javascript → javascript-node
            objective-c → objective-c-clang
            py or python → python3
            swift → swift4

            After this processing, the `run` command sends your code to https://tio.run
            and receives any outputs specified in your code. If you would like similar
            functionality in your terminal, check out https://github.com/wheelercj/tias
            """
        )
        paginator = Paginator("`run` guide", text.split("\n\n"), length=1)
        await paginator.run(ctx)

    @_run.command(name="languages", aliases=["l", "s", "langs", "list", "search"])
    async def list_programming_languages(self, ctx, *, query: str = None):
        """Lists languages the `run` command supports, optionally filtered

        For example, `run languages py` will only show languages that contain `py`. You
        can also see a full list of supported languages here: https://tio.run/#

        Parameters
        ----------
        query: Optional[str]
            A search term to filter by.
        """
        if query is None:
            await ctx.send(
                "You can optionally choose a search term, e.g. "
                '`run languages py` will only show languages that contain "py"'
            )
            title = "languages supported by the `run` command"
        else:
            title = f"supported languages that contain `{query}`"
        async with MyTio(session=self.bot.session) as tio:
            valid_languages: list[str] = [x.tio_name for x in await tio.get_languages()]
            valid_languages.extend((await self.get_aliases()).keys())
            valid_languages = sorted(valid_languages)
            paginator = Paginator(
                title=title, entries=valid_languages, filter_query=query
            )
            await paginator.run(ctx)

    @_run.command(name="jargon", aliases=["j"])
    async def send_jargon(self, ctx, language: str):
        """Shows the jargon the `run` command uses for a language

        Parameters
        ----------
        language: str
            The programming language to view commonly reused code of.
        """
        jargon: dict[str, tuple[str, str]] = await self.get_jargon()
        if language not in jargon:
            raise commands.BadArgument(
                f"No jargon wrapping has been set for the `{language}` language"
            )
        await ctx.send(
            f"`jargon:`\n{jargon[language][0]}"
            f"\n`jargon key:`\n{jargon[language][1]}"
        )

    async def parse_exec_language(
        self, language: str, expression: str
    ) -> tuple[str, str]:
        """Changes some language names and wraps jargon for some languages.

        Changing some language names is important for TIO.
        """
        aliases: dict[str, str] = await self.get_aliases()
        if language in aliases:
            language = aliases[language]
        jargon: dict[str, tuple[str, str]] = await self.get_jargon()
        if language in jargon and jargon[language][1] not in expression:
            expression = jargon[language][0].replace("INSERT_HERE", expression, 1)
        return language, expression

    async def get_aliases(self) -> dict[str, str]:
        return {
            "c": "c-clang",
            "c#": "cs-csc",
            "c++": "cpp-clang",
            "cpp": "cpp-clang",
            "cs": "cs-csc",
            "f#": "fs-core",
            "fs": "fs-core",
            "java": "java-openjdk",
            "javascript": "javascript-node",
            "js": "javascript-node",
            "objective-c": "objective-c-clang",
            "py": "python3",
            "python": "python3",
            "swift": "swift4",
        }

    async def get_jargon(self) -> dict[str, tuple[str, str]]:
        jargon: dict[str, tuple[str, str]] = {
            # keys: the language
            # values:
            #   * the jargon
            #   * the "jargon key"
            "c": (
                dedent(
                    """\
                    #include <stdbool.h>
                    #include <stdio.h>
                    int main(void) {
                        INSERT_HERE
                    }\
                    """
                ),
                "int main(",
            ),
            "cpp": (
                dedent(
                    """\
                    #include <iostream>
                    #include <stdio.h>
                    using namespace std;
                    int main() {
                        INSERT_HERE
                    }\
                    """,
                ),
                "int main(",
            ),
            "cs": (
                dedent(
                    """\
                    namespace MyNamespace {
                        class MyClass {
                            static void Main(string[] args) {
                                INSERT_HERE
                            }
                        }
                    }\
                    """
                ),
                "static void Main(",
            ),
            "dart": (
                dedent(
                    """\
                    void main() {
                        INSERT_HERE
                    }\
                    """
                ),
                "void main(",
            ),
            "go": (
                dedent(
                    """\
                    package main
                    import "fmt"
                    func main() {
                        INSERT_HERE
                    }\
                    """
                ),
                "func main(",
            ),
            "java": (
                dedent(
                    """\
                    import java.util.*;
                    class MyClass {
                        public static void main(String[] args) {
                            Scanner scanner = new Scanner(System.in);
                            INSERT_HERE
                        }
                    }\
                    """
                ),
                "public static void main(",
            ),
            "kotlin": (
                dedent(
                    """\
                    fun main(args : Array<String>) {
                        INSERT_HERE
                    }\
                    """
                ),
                "fun main(",
            ),
            "objective-c": (
                dedent(
                    """\
                    #include <stdio.h>
                    // Print with the `puts` function, not `NSLog`.
                    int main() {
                        INSERT_HERE
                    }\
                    """
                ),
                "int main(",
            ),
            "rust": (
                dedent(
                    """\
                    fn main() {
                        INSERT_HERE
                    }\
                    """
                ),
                "fn main(",
            ),
            "scala": (
                dedent(
                    """\
                    object Main extends App {
                        INSERT_HERE
                    }\
                    """
                ),
                "object Main",
            ),
        }
        jargon["c-clang"] = jargon["c"]
        jargon["c-gcc"] = jargon["c"]
        jargon["c-tcc"] = jargon["c"]
        jargon["c#"] = jargon["cs"]
        jargon["c++"] = jargon["cpp"]
        jargon["cpp-clang"] = jargon["cpp"]
        jargon["cpp-gcc"] = jargon["cpp"]
        jargon["cs-core"] = jargon["cs"]
        jargon["cs-csc"] = jargon["cs"]
        jargon["cs-csi"] = jargon["cs"]
        jargon["cs-mono-shell"] = jargon["cs"]
        jargon["cs-mono"] = jargon["cs"]
        jargon["java-jdk"] = jargon["java"]
        jargon["java-openjdk"] = jargon["java"]
        jargon["objective-c-clang"] = jargon["objective-c"]
        jargon["objective-c-gcc"] = jargon["objective-c"]
        return jargon

    ###########################
    # translate command group #
    ###########################

    @commands.hybrid_group(
        aliases=["trans", "translation"], invoke_without_command=True
    )
    async def translate(self, ctx, *, words: str):
        """A group of commands for translating between languages

        Without a subcommand, this command translates words from any language (auto-
        detected) to English.

        Parameters
        ----------
        words: str
            The message to translate.
        """
        translated = await self._translate("auto", "en", words)
        embed = discord.Embed(title="English translation", description=translated)
        await ctx.send(embed=embed)

    @translate.command(name="to")
    async def translate_to(self, ctx, to_language: str, *, words: str):
        """Translates words from any language (auto-detected) to a chosen language

        Parameters
        ----------
        to_language: str
            The language to translate to.
        words: str
            The message to translate.
        """
        translated = await self._translate("auto", to_language, words)
        embed = discord.Embed(
            title=f"{to_language} translation", description=translated
        )
        await ctx.send(embed=embed)

    @translate.command(name="from")
    async def translate_from(
        self, ctx, from_language: str, to_language: str, *, words: str
    ):
        """Translates words from a chosen language to a chosen language

        Parameters
        ----------
        from_language: str
            The language to translate from.
        to_language: str
            The language to translate to.
        words: str
            The message to translate.
        """
        translated = await self._translate(from_language, to_language, words)
        embed = discord.Embed(
            title=f"{to_language} translation", description=translated
        )
        await ctx.send(embed=embed)

    async def _translate(self, from_language: str, to_language: str, words: str) -> str:
        """Translates words from one language to another

        Raises commands.BadArgument if a language is not recognized or a translation is
        not found.
        """
        # https://pypi.org/project/deep-translator/
        try:
            translated = GoogleTranslator(
                source=from_language, target=to_language
            ).translate(words)
        except LanguageNotSupportedException:
            raise commands.BadArgument("Language not found.")
        except TranslationNotFound:
            raise commands.BadArgument("Translation not found.")
        return translated

    @translate.command(name="languages", aliases=["l", "s", "langs", "list", "search"])
    async def list_translation_languages(self, ctx, *, query: str = None):
        """Lists the languages supported by the translate commands

        Parameters
        ----------
        query: Optional[str]
            A search term to filter by.
        """
        languages = GoogleTranslator.get_supported_languages()
        if query:
            title = f"languages that contain `{query}`"
        else:
            title = "languages supported by the translate commands"
        paginator = Paginator(title=title, entries=languages, filter_query=query)
        await paginator.run(ctx)

    #################
    # word commands #
    #################

    @commands.hybrid_command(aliases=["def", "definition", "definitions"])
    async def define(self, ctx, word: str):
        """Lists definitions of a given word

        Parameters
        ----------
        word: str
            The word to see a definition of.
        """
        # https://github.com/johnbumgarner/wordhoard
        definition = Definitions(word)
        try:
            results = definition.find_definitions()
        except SystemExit:
            raise RuntimeError("wordhoard could not connect to its sources")
        title = f"definition of `{word}`"
        await self.send_word_results(ctx, results, title)

    @commands.hybrid_command(aliases=["syno", "synonym"])
    async def synonyms(self, ctx, word: str):
        """Lists words with the same or similar meaning to a given word

        Parameters
        ----------
        word: str
            The word to see synonyms of.
        """
        synonym = Synonyms(word)
        try:
            results = synonym.find_synonyms()
        except SystemExit:
            raise RuntimeError("wordhoard could not connect to its sources")
        title = f"synonyms of `{word}`"
        await self.send_word_results(ctx, results, title)

    @commands.hybrid_command(aliases=["anto", "antonym"])
    async def antonyms(self, ctx, word: str):
        """Lists words with the opposite meaning as a given word

        Parameters
        ----------
        word: str
            The word to see antonyms of.
        """
        antonym = Antonyms(word)
        try:
            results = antonym.find_antonyms()
        except SystemExit:
            raise RuntimeError("wordhoard could not connect to its sources")
        title = f"antonyms of `{word}`"
        await self.send_word_results(ctx, results, title)

    @commands.hybrid_command(aliases=["hyper", "hypernym"], hidden=True)
    async def hypernyms(self, ctx, word: str):
        """Lists words of more general meaning than a given word

        Parameters
        ----------
        word: str
            The word to see hypernyms of.
        """
        hypernym = Hypernyms(word)
        try:
            results = hypernym.find_hypernyms()
        except SystemExit:
            raise RuntimeError("wordhoard could not connect to its sources")
        title = f"hypernyms of `{word}`"
        await self.send_word_results(ctx, results, title)

    @commands.hybrid_command(aliases=["hypo", "hyponym"], hidden=True)
    async def hyponyms(self, ctx, word: str):
        """Lists words of more specific meaning than a given word

        Parameters
        ----------
        word: str
            The word to see hyponyms of.
        """
        hyponym = Hyponyms(word)
        try:
            results = hyponym.find_hyponyms()
        except SystemExit:
            raise RuntimeError("wordhoard could not connect to its sources")
        title = f"hyponyms of `{word}`"
        await self.send_word_results(ctx, results, title)

    @commands.hybrid_command(aliases=["homo", "homophone"], hidden=True)
    async def homophones(self, ctx, word: str):
        """Lists words that sound the same as a given word

        Parameters
        ----------
        word: str
            The word to see homophones of.
        """
        homophone = Homophones(word)
        try:
            results = homophone.find_homophones()
        except SystemExit:
            raise RuntimeError("wordhoard could not connect to its sources")
        if results and not isinstance(results, str):
            for i, result in enumerate(results):
                results[i] = result.split()[-1]
        title = f"homophones of `{word}`"
        await self.send_word_results(ctx, results, title)

    async def send_word_results(self, ctx, results: list[str], title: str) -> None:
        """Bullet-points and paginates a list of strings in ctx"""
        if not results or isinstance(results, str):
            raise commands.BadArgument("No results found.")
        paginator = Paginator(
            title=title,
            entries=results,
            prefix="• ",
        )
        await paginator.run(ctx)

    @commands.hybrid_command(name="auto-incorrect", aliases=["ai", "autoincorrect"])
    async def auto_incorrect(self, ctx, *, words: str):
        """Replaces as many words as possible with other words that sound the same

        Parameters
        ----------
        words: str
            The message to replace words in.
        """
        results = []
        for word in words.split():
            homophone = Homophones(word)
            try:
                result_sentences = homophone.find_homophones()
            except SystemExit:
                raise RuntimeError("wordhoard could not connect to its sources")
            if not result_sentences or isinstance(result_sentences, str):
                results.append(word)
            else:
                results.append(result_sentences[0].split()[-1])
        await ctx.send(" ".join(results))

    #######################
    # quote command group #
    #######################

    @commands.hybrid_group(invoke_without_command=True)
    async def quote(self, ctx, *, time: str = None):
        """Shows a random famous quote

        If a time is provided in hh:mm format, a quote will be sent each day at that
        time. You can cancel daily quotes with `quote stop`. If you have not chosen a
        timezone with the `timezone set` command, UTC will be assumed.

        Parameters
        ----------
        time: Optional[str]
            The time at which to receive a random quote each day.
        """
        cmd = self.bot.get_command("quote get")
        await ctx.invoke(cmd, time=time)

    @quote.command()
    async def get(self, ctx, *, time: str = None):
        """Shows a random famous quote

        If a time is provided in hh:mm format, a quote will be sent each day at that
        time. You can cancel daily quotes with `quote stop`. If you have not chosen a
        timezone with the `timezone set` command, UTC will be assumed.

        Parameters
        ----------
        time: Optional[str]
            The time at which to receive a random quote each day.
        """
        if time is None:
            await self.send_quote(ctx, ctx.author.id)
            return
        if not await self.bot.is_owner(ctx.author):
            raise commands.BadArgument(
                "This command can be used freely without a time, but setting a daily"
                " quote time is temporarily owner-only while bugs are being fixed."
            )
        if time.count(":") != 1 or time[-1] == ":":
            raise commands.BadArgument(
                "Please enter a time in HH:mm format. You may use 24-hour time or"
                " either AM or PM."
            )
        dt, _ = await parse_time_message(ctx, time)
        now = datetime.now(timezone.utc)
        target_time = datetime(
            now.year,
            now.month,
            now.day,
            int(dt.hour),
            int(dt.minute),
            tzinfo=timezone.utc,
        )
        if target_time < now:
            target_time += timedelta(days=1)
        await self.save_daily_quote_to_db(ctx, now, target_time)
        if self.running_quote_info is None:
            self.quotes_task = self.bot.loop.create_task(self.run_daily_quotes())
        elif target_time < self.running_quote_info.target_time:
            self.quotes_task.cancel()
            self.quotes_task = self.bot.loop.create_task(self.run_daily_quotes())
        timestamp = await create_short_timestamp(target_time)
        await ctx.send(
            f"Time set! At {timestamp} each day, I will send you a random quote."
        )

    @quote.command(name="stop", aliases=["del", "delete"])
    async def stop_daily_quote(self, ctx):
        """Stops your daily quotes"""
        try:
            await self.bot.db.execute(
                """
                DELETE FROM daily_quotes
                WHERE author_id = $1;
                """,
                ctx.author.id,
            )
            if (
                self.running_quote_info is not None
                and ctx.author.id == self.running_quote_info.author_id  # noqa: W503
            ):
                self.quotes_task.cancel()
                self.quotes_task = self.bot.loop.create_task(self.run_daily_quotes())
        except Exception as e:
            await safe_send(ctx, f"Error: {e}", protect_postgres_host=True)
        else:
            await ctx.send("Your daily quotes have been stopped.")

    @quote.command(name="mod-delete", aliases=["mdel", "moddelete"])
    @commands.has_guild_permissions(manage_messages=True)
    async def mod_delete_daily_quote(self, ctx, *, member: discord.Member):
        """Stops the daily quotes of anyone on this server

        Parameters
        ----------
        member: discord.Member
            The member to delete a running daily quote of.
        """
        try:
            await self.bot.db.execute(
                """
                DELETE FROM daily_quotes
                WHERE author_id = $1
                    AND server_id = $2;
                """,
                member.id,
                ctx.guild.id,
            )
            if (
                self.running_quote_info is not None
                and member.id == self.running_quote_info.author_id  # noqa: W503
            ):
                self.quotes_task.cancel()
                self.quotes_task = self.bot.loop.create_task(self.run_daily_quotes())
        except Exception as e:
            await safe_send(ctx, f"Error: {e}", protect_postgres_host=True)
        else:
            await ctx.send(f"{member.display_name}'s daily quotes have been stopped.")

    @quote.command(name="list", aliases=["l"])
    @commands.guild_only()
    async def list_daily_quote(self, ctx):
        """Lists everyone that set up daily quotes in this channel"""
        try:
            records = await self.bot.db.fetch(
                """
                SELECT *
                FROM daily_quotes
                WHERE server_id = $1
                    AND channel_id = $2;
                """,
                ctx.guild.id,
                ctx.channel.id,
            )
        except Exception as e:
            await safe_send(ctx, f"Error: {e}", protect_postgres_host=True)
            return
        if records is None or not len(records):
            raise commands.UserInputError(
                "There are no daily quotes set up in this channel."
            )
        message = "Here's everyone that set up a daily quote in this channel:"
        for r in records:
            member = ctx.guild.get_member(r["author_id"])
            if member:
                name = f"{member.name}#{member.discriminator}"
            else:
                name = r["author_id"]
            message += "\n" + name
        await ctx.send(message)

    async def save_daily_quote_to_db(
        self, ctx, start_time: datetime, target_time: datetime
    ) -> None:
        """Saves one daily quote to the database"""
        if ctx.guild:
            is_dm = False
            server_id = ctx.guild.id
            channel_id = ctx.channel.id
        else:
            is_dm = True
            server_id = 0
            channel_id = 0
        await self.bot.db.execute(
            """
            INSERT INTO daily_quotes
            (author_id, start_time, target_time, is_dm, server_id, channel_id)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (author_id)
            DO UPDATE
            SET target_time = $3,
                is_dm = $4,
                server_id = $5,
                channel_id = $6
            WHERE daily_quotes.author_id = $1;
            """,
            ctx.author.id,
            start_time,
            target_time,
            is_dm,
            server_id,
            channel_id,
        )

    async def get_next_quote_info(
        self,
    ) -> tuple[Optional[datetime], Optional[int], Optional[Messageable]]:
        """Gets from the database the info for the nearest (in time) daily quote task

        Returns (target_time, author_id, destination).
        If there is no next daily quote, this function returns (None, None, None).
        """
        r = await self.bot.db.fetchrow(
            """
            SELECT *
            FROM daily_quotes
            ORDER BY target_time
            LIMIT 1;
            """
        )
        if r is None:
            return None, None, None
        target_time = r["target_time"]
        author_id = r["author_id"]
        if r["is_dm"]:
            destination = self.bot.get_user(r["author_id"])
        else:
            server = self.bot.get_guild(r["server_id"])
            destination = server.get_channel(r["channel_id"])
        return target_time, author_id, destination

    async def update_quote_target_time(
        self, old_target_time: datetime, author_id: int
    ) -> None:
        """Changes a daily quote's target time in the database to one day later"""
        new_target_time = old_target_time + timedelta(days=1)
        await self.bot.db.execute(
            """
            UPDATE daily_quotes
            SET target_time = $1
            WHERE author_id = $2
            """,
            new_target_time,
            author_id,
        )

    async def send_quote(self, destination: Messageable, requester_id: int) -> None:
        """Immediately sends a random quote to destination

        May raise ContentTypeError or json.decoder.JSONDecodeError.
        """
        quote, author = await self.get_quote()
        requester = self.bot.get_user(requester_id)
        if requester:
            requester_name = requester.name + "#" + requester.discriminator
        else:
            requester_name = requester_id
        embed = discord.Embed(description=f'"{quote.strip()}"\n — {author}')
        embed.set_footer(text=f"Requested by {requester_name}")
        await destination.send(embed=embed)

    async def get_quote(self) -> tuple[str, str]:
        """Gets a quote and the quote's author from the forismatic API

        May raise ContentTypeError or json.decoder.JSONDecodeError.
        """
        params = {"lang": "en", "method": "getQuote", "format": "json"}
        async with self.bot.session.get(
            "http://api.forismatic.com/api/1.0/", params=params
        ) as response:
            json_text = await response.json()
        quote = json_text["quoteText"]
        author = json_text["quoteAuthor"]
        return quote, author


async def setup(bot):
    await bot.add_cog(Other(bot))
