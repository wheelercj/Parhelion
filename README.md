# Parhelion

A general-purpose Discord bot that can send reminders, help with answering FAQs, translate between many different languages, solve math questions, run code in just about any language, and more.

![demo gif](https://media.giphy.com/media/ydzwjHvEZEc2kmi049/giphy.gif)

You can try the bot in [the support server](https://discord.gg/mCqGhPJVcN), or [invite](https://discord.com/oauth2/authorize?client_id=836071320328077332&scope=bot+applications.commands&permissions=2147740736) the bot into your own server, or run your own instance of the bot by following one of the two sets of instructions below.

Parhelion is tested with Python 3.11.

## local hosting setup

1. `git clone https://github.com/wheelercj/Parhelion.git`.
2. Optionally create a virtual environment.
3. `pip install -r requirements.txt`.
4. Optionally, `pip install -r requirements-dev.txt` and `pre-commit install`.
5. Create a `.env` file in the project's root with the environment variables described in the next steps.
6.  Create a [Discord API Application](https://discord.com/developers/applications) and an environment variable for it called `discord_bot_secret_token`. Enable the server members intent and the message content intent. You can see which permissions the bot needs in the `get_bot_invite_link` function near the top of [cogs/utils/common.py](https://github.com/wheelercj/Parhelion/blob/main/cogs/utils/common.py).
7.  Create a PostgreSQL server and a `postgres_password` environment variable. If you will use postgres credentials different from the postgres defaults, also create other environment variables as necessary: `postgres_host`, `postgres_database`, `postgres_port`, `postgres_user`.
8.  [Create a GitHub personal access token](https://gist.github.com/beep-boop-82197842/4255864be63966b8618e332d1df30619) for making gists, and environment variables called `alternate_github_gists_token` and `alternate_github_account_name`. These are used to automatically create gists of any leaked bot tokens Parhelion detects to invalidate the tokens and protect Discord bots (including itself). You might want to create a separate GitHub account for this.
9.  If you will use the owner-only `gist` command, create a GitHub personal access token for making gists and an environment variable called `main_github_gists_token`.
10. Change the bot's developer settings in the `DevSettings` class near the top of common.py.
11. Run main.py.

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
17. `pip install -r requirements.txt`. It's probably best to not use a virtual environment because they don't work well with systemd.
18. Optionally, `pip install -r requirements-dev.txt` and `pre-commit install`.
19. Create a `.env` file in the project's root with the environment variables described in the next steps.
20. Create a [Discord API Application](https://discord.com/developers/applications) and an environment variable for it called `discord_bot_secret_token`. Enable the server members intent and the message content intent. You can see which permissions the bot needs in the `get_bot_invite_link` function near the top of [cogs/utils/common.py](https://github.com/wheelercj/Parhelion/blob/main/cogs/utils/common.py).
21. [Create a PostgreSQL server](https://docs.fedoraproject.org/en-US/quick-docs/postgresql/) and a `postgres_password` environment variable. If you will use postgres credentials different from the postgres defaults, also create other environment variables as necessary: `postgres_host`, `postgres_database`, `postgres_port`, `postgres_user`.
22. [Create a GitHub personal access token](https://gist.github.com/beep-boop-82197842/4255864be63966b8618e332d1df30619) for making gists, and environment variables called `alternate_github_gists_token` and `alternate_github_account_name`. These are used to automatically create gists of any leaked bot tokens Parhelion detects to invalidate the tokens and protect Discord bots (including itself). You might want to create a separate GitHub account for this.
23. If you will use the owner-only `gist` command, create a GitHub personal access token for making gists and an environment variable called `main_github_gists_token`.
24. Change the bot's developer settings in the `DevSettings` class near the top of common.py.
25. Create a new systemd service unit file named mybot.service with `sudo systemctl edit --force --full mybot.service` with the contents shown below. The file should appear in `/etc/systemd/system/`.
26. Reload systemd with `sudo systemctl daemon-reload`.
27. Start the bot with `sudo systemctl start mybot`.
28. Make sure `mybot.service` doesn't have a "failed" status shown with `systemctl status mybot.service`. If the service failed, use `journalctl -u mybot.service` to see more details. [This systemd guide](https://www.digitalocean.com/community/tutorials/systemd-essentials-working-with-services-units-and-the-journal) might help as well.
29. Make the bot automatically start on boot with `sudo systemctl enable mybot`.

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
