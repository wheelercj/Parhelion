# Parhelion

A general-purpose Discord bot that can send reminders, help with answering FAQs, translate between many different languages, solve math questions, run code in just about any programming language, and more.

You can try the bot in [the support server](https://discord.gg/mCqGhPJVcN), [invite](https://discord.com/oauth2/authorize?client_id=836071320328077332&scope=bot+applications.commands&permissions=257088) the bot into your own server, or run your own instance of the bot by following the instructions below.

## local hosting setup

Parhelion is tested with Python 3.10.

1. `git clone https://github.com/wheelercj/Parhelion.git`
2. Optionally create a virtual environment.
3. `pip install -r requirements.txt`.
4. Optionally, `pip install -r requirements-dev.txt` and `pre-commit install`.
5. Create a `.env` file in the project's root with the environment variables described in the next steps.
6. Create a [Discord API Application](https://discord.com/developers/applications) and an environment variable for it called `DISCORD_BOT_SECRET_TOKEN`.
7. Create a PostgreSQL server and environment variables:
   * `PostgreSQL_user`
   * `PostgreSQL_host`
   * `PostgreSQL_database`
   * `PostgreSQL_password`
8. [Create a GitHub personal access token](https://gist.github.com/beep-boop-82197842/4255864be63966b8618e332d1df30619) for making gists and environment variables called `ALTERNATE_GITHUB_GISTS_TOKEN` and `ALTERNATE_GITHUB_ACCOUNT_NAME`. These are used to automatically create gists of any leaked secret tokens the bot detects to invalidate the tokens and protect Discord bots. You may want to create a separate GitHub account for this.
9. If you will use the owner-only `gist` command, create a GitHub personal access token for making gists and an environment variable called `MAIN_GITHUB_GISTS_TOKEN`.
10. Change the bot's developer settings in the `DevSettings` class near the top of settings.py.
11. Run main.py.

## examples

Here are some (slightly outdated) samples of what the bot can do:

![help menu](docs/help%20menu.png)

![Other help](docs/Other%20help.png)

![tag help](docs/tag%20help.png)

![remind help](docs/remind%20help.png)

![set help](docs/set%20help.png)

![Info help](docs/Info%20help.png)
