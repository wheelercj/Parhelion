# TODO

## rate and request limits security
* Use the logging module to log info like which commands were used when.
* Track the rate of invalid requests.
* Set cooldowns on commands and global cooldowns on people.

## other
* Add more info to the web page that shows up when people run the bot on the spotlight page. Is it possible to have the program copy the contents of the readme and put them into the site?

## improve reminders
* Use the replit database to store the reminders instead of reminders.txt? (https://docs.replit.com/misc/database)
  * Or find a way to encrypt reminders.txt? Replit files are completely public, somewhat unlike Discord messages. Is it possible to save reminders in replit secrets? Probably not.
* Add a way for a user to list their active reminders. Show remaining time.
* Add a way for a user to cancel their active reminders. A reaction button on the bot's reply to the creation of the reminder?
