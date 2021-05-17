# TODO

## figure out how to host the bot safely
* Confirm whether repl.it forces the users of a bot to share an IP address, and whether discord bans IP addresses from their API for overuse. (Side note: does GitHub's APIs do this too? Do all APIs do this?) 
* Use the logging module to log info like which commands are used when.
* Maybe if I keep the instance of this bot that's on replit simple, and I set cooldowns on commands and global cooldowns on people, the API's limit will not be hit? What are the API limits?
* or host the bot somewhere else \[\[20210516152852]]

## other
* Add more info to the web page that shows up when people run the bot on the spotlight page. Is it possible to have the program copy the contents of the readme and put them into the site?

## improve reminders
* When a new reminder is created, repeat the reminder content and time back to the creator.
* Use the replit database to store the reminders instead of reminders.txt? (https://docs.replit.com/misc/database)
	* Find a way to encrypt reminders.txt? Replit files are completely public, somewhat unlike Discord messages. Is it possible to save reminders in replit secrets? Probably not.
* Add a way for a user to list their active reminders? Show remaining time?
* Add a way for a user to cancel their active reminders? A reaction button on the bot's reply to the creation of the reminder?
