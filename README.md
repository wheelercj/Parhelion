# Parhelion

A general-purpose Discord bot that can send reminders, help with answering FAQs, translate between many different languages, solve math questions, run code in just about any language, and more.

![demo gif](https://media.giphy.com/media/ydzwjHvEZEc2kmi049/giphy.gif)

You can try the bot in [the support server](https://discord.gg/mCqGhPJVcN), or [invite](https://discord.com/oauth2/authorize?client_id=836071320328077332&scope=bot+applications.commands&permissions=2147740736) the bot into your own server, or run your own instance of the bot by following the instructions below.

## setup instructions using docker

coming soon

## local hosting setup

1. `git clone https://github.com/wheelercj/Parhelion.git`.
2. Optionally, create a virtual environment such as with `py -3.11 -m venv venv` or `python3.11 -m venv venv`, and [activate the virtual environment](https://python.land/virtual-environments/virtualenv).
3. `pip install -r requirements.txt` to install the dependencies.
4.  Create a [Discord API Application](https://discord.com/developers/applications). Enable the server members intent and the message content intent. You can see which permissions the bot needs in the `get_bot_invite_link` function near the top of [cogs/utils/common.py](https://github.com/wheelercj/Parhelion/blob/main/cogs/utils/common.py).
5.  Create a PostgreSQL server.
6.  Create a file named `.env` in the project's root. See the sample .env file below for what to put in the file.
7.  Run main.py.

## remote hosting setup

This guide shows one of many possible ways to set up Parhelion on a remote server, using a VPS that is indefinitely free but requires a credit card number.

1. Create an "Always Free" instance on [Oracle Cloud's free tier](https://www.oracle.com/cloud/free/). Oracle Linux is very similar to Fedora.
2. [Connect to the instance](https://docs.oracle.com/en-us/iaas/Content/Compute/Tasks/accessinginstance.htm).
3. `sudo dnf update && sudo dnf upgrade -y` to update the operating system. This will take a while.
4. `sudo dnf install git`.
5. `sudo dnf install gcc openssl-devel bzip2-devel libffi-devel zlib-devel wget make -y` to install the Python language compilation dependencies.
6. Navigate to where you want Python installed.
7. `wget https://www.python.org/ftp/python/3.10.0/Python-3.10.0.tar.xz` to download Python's code.
8. `tar -xf Python-3.10.0.tar.xz` to unzip/extract the downloaded Python files.
9. `cd Python-3.10.0 && ./configure --enable-optimizations`.
10. `nproc` to find out how many cores the system has.
11. `make -j <number_of_cores>` to compile Python. This will take a while.
12. `sudo make altinstall`.
13. `python3.10 --version` to confirm that Python has installed correctly.
14. `python3.10 -m pip install --upgrade pip`.
15. Navigate to where you want a folder of Parhelion's code to appear.
16. `git clone https://github.com/wheelercj/Parhelion.git`.
17. `pip install -r requirements.txt` to install the dependencies. It's probably best to not use a virtual environment because they don't work well with systemd.
18. Create a [Discord API Application](https://discord.com/developers/applications). Enable the server members intent and the message content intent. You can see which permissions the bot needs in the `get_bot_invite_link` function near the top of [cogs/utils/common.py](https://github.com/wheelercj/Parhelion/blob/main/cogs/utils/common.py).
19. [Create a PostgreSQL server](https://docs.fedoraproject.org/en-US/quick-docs/postgresql/).
20. Create a file named `.env` in the project's root. See the sample .env file below for what to put in the file.
21. Create a new systemd service unit file named mybot.service with `sudo systemctl edit --force --full mybot.service` with the contents shown below. The file should appear in `/etc/systemd/system/`.
22. Reload systemd with `sudo systemctl daemon-reload`.
23. Start the bot with `sudo systemctl start mybot`.
24. Make sure `mybot.service` doesn't have a "failed" status shown with `systemctl status mybot.service`. If the service failed, use `journalctl -u mybot.service` to see more details. [This systemd guide](https://www.digitalocean.com/community/tutorials/systemd-essentials-working-with-services-units-and-the-journal) might help as well.
25. Make the bot automatically start on boot with `sudo systemctl enable mybot`.

**mybot.service**

```
[Unit]
Description=Parhelion
After=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/opc/Parhelion
ExecStart=python3.10 /home/opc/Parhelion/main.py
User=opc
Restart=on-failure
StartLimitInterval=30

[Install]
WantedBy=multi-user.target
```

## sample .env

Here's an example of a .env file for this bot based on the real one Parhelion uses (all the secrets in this example have been replaced with fakes).

```Dotenv
# The only variables required for the bot to run are DISCORD_BOT_TOKEN,
# POSTGRES_PASSWORD, and PRIVACY_POLICY_LINK. Some variables are required for certain
# features and/or have default values defined elsewhere you may want to change as
# described below. Most of the remaining variables you will probably want to
# comment-out, delete, or change the value of.

# Get this from the Discord API app page: https://discord.com/developers/applications
DISCORD_BOT_TOKEN="BfnYJ4XscOQOIkC5bxUbr3QH.D9yps5.cfURLTidT_zCPRZ-DxcaUMk634E"

PRIVACY_POLICY_LINK="https://gist.github.com/wheelercj/033bbaf78b08ff0335943d5119347853"

# The Postgres variables, if removed, default to the Postgres defaults (except password;
# there is no default password).
POSTGRES_HOST="localhost"
POSTGRES_PORT=5432
POSTGRES_DB="bot"
POSTGRES_USER="dev"
POSTGRES_PASSWORD="dkByXjCEQJ7UPYgyZu1W167LhldOVcSgEV7EXmhs7iYbzf4yv73tmIzYlmqvSQHYZrLo7se8lbOR3FYIFBzJv6NgDwg5GBj4FZIc"

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
SUPPORT_SERVER_ID=845465081582977044

MEMBERSHIP_LINK="https://ko-fi.com/parhelion99369"
MEMBERSHIP_REMOVES_NOTE_LIMIT=true
MEMBERSHIP_REMOVES_REMINDER_LIMIT=true
MEMBERSHIP_REMOVES_TAG_LIMIT=true
MEMBERSHIP_ROLE_IDS="884564744722333697,884565844221382668,884565211632267285"
```
