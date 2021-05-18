# TODO

## rate and request limits security
* Track the rate of invalid requests. (made where?)
* Set global cooldowns on people.

## other
* Add more info to the web page that shows up when people run the bot on the spotlight page. Is it possible to have the program copy the contents of the readme and put them into the site?
* make commands.py a cog called "Other"?
* Put the dev and/or the hidden commands in another cog?
* Add to the doc command: if KeyError, try to guess which docs might have been meant and suggest them.
* How often do bot developers tend to restart the bot's server? I could be interrupting use of the stream command each time.

## improve reminders
* Use the replit database to store the reminders instead of reminders.txt? (https://docs.replit.com/misc/database)
  * Or find a way to encrypt reminders.txt? Replit files are completely public, somewhat unlike Discord messages. Is it possible to save reminders in replit secrets? Probably not.
* Add a way for a user to list their active reminders. Show remaining time.
* Add a way for a user to cancel their active reminders. A reaction button on the bot's reply to the creation of the reminder?
