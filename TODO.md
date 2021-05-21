# TODO

## rate and request limits security
* Track the rate of invalid requests (made to the discord API?).
* Set global cooldowns on people.

## other
* Add more info to the web page that shows up when people run the bot on the spotlight page. Is it possible to have the program copy the contents of the readme and put them into the site?
* Use the [forismatic API](https://forismatic.com/en/api/) for the quote command?
* Add to the doc command: if KeyError, try to guess which docs might have been meant and suggest them.

## improve reminders
* Add a way for a user to delete their active reminders.
* Add a way for a user to list their active reminders. Show remaining time.
* Use [discord.py tasks](https://discordpy.readthedocs.io/en/latest/ext/tasks/index.html?highlight=task) to run the reminders?
* Use the [replit database](https://docs.replit.com/misc/database) to store the reminders instead of reminders.txt?
