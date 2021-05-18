# Parhelion

A simple Discord bot that can play music, solve math questions, and send reminders.

![demo](images/demo.png)

## how to add this bot
There are two ways you can add this bot to Discord servers where you have "manage server" permissions:

1. By adding my instance of the bot to your server by clicking [this link](https://discordapp.com/api/oauth2/authorize?scope=bot&client_id=836071320328077332&permissions=3300352).
2. By making a fork of this repl and creating your own instance of the bot. You will need to create a Discord bot account ([see this guide](https://www.freecodecamp.org/news/create-a-discord-bot-with-python/)), and then set a Repl.it environment variable called `DISCORD_BOT_SECRET_TOKEN` as explained [here](https://docs.replit.com/repls/secrets-environment-variables)
(no changes to the code or an env file are necessary; this is just in Repl.it's menu). To keep the bot running continuously without Repl.it's premium "always on" option, you can use a free UptimeRobot account as explained in the first guide linked above.

After adding this bot, you can see a full list of commands by entering `;help`.

## guides
Here are some guides to making Discord bots that I found helpful:
* https://ritza.co/showcase/repl.it/building-a-discord-bot-with-python-and-repl-it.html
* https://www.freecodecamp.org/news/create-a-discord-bot-with-python/
* https://discordpy.readthedocs.io/en/latest/index.html
* https://github.com/Rapptz/discord.py/tree/v1.7.1/examples
* https://discord.com/developers/docs/intro

## commands
Below is a list of the commands that this bot has as of May 16, 2021. This image will not always be kept up-to-date.

![help demo](images/help_demo.png)

## optional environment variables
If you make a fork of this bot, the only environment variable you will need to set is `DISCORD_BOT_SECRET_TOKEN`, as explained above. However, there is an optional environment variable you can set: `MY_CHANNEL_ID`. This lets you use the `dev_mail` async function. Choose the Discord channel where you want to receive high-priority messages from the bot. The `dev_mail` async function is only called to alert the developer in situations like when the bot joins a new server, or cannot recover from certain errors without your help.
