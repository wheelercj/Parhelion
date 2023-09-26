# Parhelion

A general-purpose Discord bot that can send reminders, help with answering FAQs, translate between many different languages, solve math questions, run code in just about any language, and more.

![demo gif](https://media.giphy.com/media/ydzwjHvEZEc2kmi049/giphy.gif)

You can try the bot in [the support server](https://discord.gg/mCqGhPJVcN), or [invite](https://discord.com/oauth2/authorize?client_id=836071320328077332&scope=bot+applications.commands&permissions=2147740736) the bot into your own server, or run your own instance of the bot by following the instructions below.

## setup instructions

These instructions use [Docker](https://www.docker.com/).

1. Create a [Discord API app](https://discord.com/developers/applications). Enable the server members intent and the message content intent. You can see which permissions the bot needs in the `get_bot_invite_link` function near the top of [cogs/utils/common.py](https://github.com/wheelercj/Parhelion/blob/main/cogs/utils/common.py).
2. Download the [`docker-compose.yml`](docker-compose.yml) file from this repo into a folder for the bot.
3. Create a file named `.env` in the project's root. See the sample .env file below for what to put in the file.
4. `docker compose up -d --pull` to download the bot and database images from Docker Hub if needed, create containers, and run the bot and database.

Here are other docker commands that may be helpful:

* `docker compose ps` to list all containers and see their statuses.
* `docker compose images` to list all images.
* `docker volume ls` to list all volumes (including the volume holding the database's data).
* `docker compose logs -ft` to see the live docker logs.
* `docker compose pause` to pause the containers.
* `docker compose unpause` to unpause paused containers.
* `docker compose stop` to stop the containers (this clears their memory).
* `docker compose start` to start stopped containers.
* `docker compose down` to stop and delete the containers. The database's data will persist.
* `docker compose rm` to delete stopped containers. The database's data will persist.
* `docker compose rm -v` to delete stopped containers and all volumes (this deletes the database's data).
* See [the official docs](https://docs.docker.com/compose/reference/) for more.

### sample .env

Here's an example of a .env file for this bot based on the real one Parhelion uses (all the secrets in this example have been replaced with fakes).

```Dotenv
# The only variables required for the bot to run are DISCORD_BOT_TOKEN,
# POSTGRES_PASSWORD, and PRIVACY_POLICY_LINK. Some variables are required for certain
# features and/or have default values defined elsewhere you may want to change as
# described below. Most of the remaining variables you will probably want to
# comment-out, delete, or change the value of.

# Get the token from the Discord API app page: https://discord.com/developers/applications
DISCORD_BOT_TOKEN="BfnYJ4XscOQOIkC5bxUbr3QH.D9yps5.cfURLTidT_zCPRZ-DxcaUMk634E"

PRIVACY_POLICY_LINK="https://gist.github.com/wheelercj/033bbaf78b08ff0335943d5119347853"

# The Postgres variables, if removed, default to the Postgres defaults (except password;
# there is no default password).
POSTGRES_DB="bot"
POSTGRES_USER="dev"
POSTGRES_PASSWORD="dkByXjCEQJ7UPYgyZu1W167LhldOVcSgEV7EXmhs7iYbzf4yv73tmIzYlmqvSQHYZrLo7se8lbOR3FYIFBzJv6NgDwg5GBj4FZIc"

# These two are used by the bot, but not by the `postgres` service in docker-compose.yml
# which always uses localhost and port 5432.
POSTGRES_HOST="postgres"
POSTGRES_PORT="5432"

# This is a string of a comma-separated list of command prefixes. If you want a comma as
# part of a command prefix, use `COMMA` to say where. The command prefixes `/` and `@`
# are hardcoded.
DEFAULT_BOT_PREFIXES=";,par ,Par "

# Required by the owner-only `gist` command for making gists.
MAIN_GITHUB_GISTS_TOKEN="ghp_gHc6Zhhprk43ZGM1VNNvQmgnDxydvKxmDVfb"

# These are used to automatically create gists of any leaked bot tokens Parhelion
# detects to invalidate the tokens and protect Discord bots (including itself). You
# might want to create a separate GitHub account for this if you think a lot of tokens
# might be spammed so you don't clutter your main account.
ALTERNATE_GITHUB_GISTS_TOKEN="ghp_aPyJbZJYCXN9wS0ZGsnHPMvc40A63DUnIScH"
ALTERNATE_GITHUB_ACCOUNT_NAME="beep-boop-82197842"

SUPPORT_SERVER_LINK="https://discord.gg/mCqGhPJVcN"
SUPPORT_SERVER_ID="845465081582977044"

MEMBERSHIP_LINK="https://ko-fi.com/parhelion99369"
MEMBERSHIP_REMOVES_NOTE_LIMIT="true"
MEMBERSHIP_REMOVES_REMINDER_LIMIT="true"
MEMBERSHIP_REMOVES_TAG_LIMIT="true"
MEMBERSHIP_ROLE_IDS="884564744722333697,884565844221382668,884565211632267285"
# By default, all membership roles remove the note, reminder, and tag limits.
```
