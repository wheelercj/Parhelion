# TODO

1. test continue_reminders
1. [custom help menu](https://discord.com/channels/336642139381301249/381965515721146390/846537189163925504)
1. set [global cooldowns](https://discord.com/channels/336642139381301249/559455534965850142/843100881431429141) on individual people ([with walk_commands?](https://discord.com/channels/336642139381301249/381963689470984203/829737892087332904))
1. server-side command prefix customization
1. update the README images
1. move to a different host and set up a new [database](https://discord.com/channels/336642139381301249/381963689470984203/829738623426625536)

## other
* Only sleep for the closest reminder, and start sleeping for the next one when that one ends. Sort the reminders list by end time. When a new reminder is created, compare it to the current closest reminder to see which one is closer, and switch if necessary. Whenever a reminder is deleted with the del-r command, check whether it's the closest reminder.
* Learn more about [process management](https://discord.com/channels/336642139381301249/564950631455129636/847070818072133643) and create a command that restarts the bot.
* Add more info to the web page that shows up when people run the bot on the spotlight page.
