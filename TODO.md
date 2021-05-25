# TODO

1. fix bugs in multiple commands
1. set global cooldowns on individual people
1. custom error message for choose command
1. custom error message for del-r command
1. [custom help menu](https://discord.com/channels/336642139381301249/381965515721146390/846537189163925504)
1. switch hosts

## other
* Add more info to the web page that shows up when people run the bot on the spotlight page.
* Use the [forismatic API](https://forismatic.com/en/api/) for the quote command?

## improve reminders
* Only sleep for the closest reminder, and start sleeping for the next one when that one ends. Sort the reminders list by end time. When a new reminder is created, compare it to the current closest reminder to see which one is closer, and switch if necessary. Whenever a reminder is deleted with the del-r command, check whether it's the closest reminder.
* Use a database.
