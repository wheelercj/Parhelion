# TODO

## rate and request limits security
* Track the rate of invalid requests (made to the discord API?).
* Set global cooldowns on people.

## other
* Add more info to the web page that shows up when people run the bot on the spotlight page.
* Use the [forismatic API](https://forismatic.com/en/api/) for the quote command?

## improve reminders
* Only sleep for the closest reminder, and start sleeping for the next one when that one ends. Sort the reminders list by end time. When a new reminder is created, compare it to the current closest reminder to see which one is closer, and switch if necessary. Whenever a reminder is deleted with the del-r command, check whether it's the closest reminder.
* Use a database. The [replit database](https://docs.replit.com/misc/database), temporarily?
