# TODO

1. [custom help menu](https://discord.com/channels/336642139381301249/381965515721146390/846537189163925504)
1. set [global cooldowns](https://discord.com/channels/336642139381301249/559455534965850142/843100881431429141) on individual people ([with walk_commands?](https://discord.com/channels/336642139381301249/381963689470984203/829737892087332904))
1. update the README images
1. move to a different host and set up a new [database](https://discord.com/channels/336642139381301249/381963689470984203/829738623426625536)

## other
* Only sleep for the nearest reminder. Sort the reminders by end time. When a new reminder is created, compare it to the current nearest reminder to see which one is nearer, and switch if necessary. Whenever a reminder is deleted with the del-r command, check whether it's the nearest reminder. Note: when the bot is restarted and saved reminders are loaded, it already only sleeps for the nearest reminder. It is only the current session that this change needs to be made for.
* Learn more about [process management](https://discord.com/channels/336642139381301249/564950631455129636/847070818072133643) and create a command that restarts the bot.
