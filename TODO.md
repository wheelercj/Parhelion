# TODO

1. Parse for the [Discord API's rate limits](https://discord.com/developers/docs/topics/rate-limits) in response headers and locally prevent exceeding the limits as they change.
1. 401 responses are avoided by providing a valid token in the authorization header when required and by stopping further requests after a token becomes invalid
1. 403 responses are avoided by inspecting role or channel permissions and by not making requests that are restricted by such permissions
1. 429 responses are avoided by inspecting the rate limit headers documented above and by not making requests on exhausted buckets until after they have reset
1. Track the rate of invalid requests made to the discord API.
1. Set global cooldowns on individual people.
1. Read about [gateway rate limits](https://discord.com/developers/docs/topics/gateway#rate-limiting).
1. custom error message for choose command
1. custom error message for del-r command
1. [custom help menu](https://discord.com/channels/336642139381301249/381965515721146390/846537189163925504)

## other
* Add more info to the web page that shows up when people run the bot on the spotlight page.
* Use the [forismatic API](https://forismatic.com/en/api/) for the quote command?

## improve reminders
* Only sleep for the closest reminder, and start sleeping for the next one when that one ends. Sort the reminders list by end time. When a new reminder is created, compare it to the current closest reminder to see which one is closer, and switch if necessary. Whenever a reminder is deleted with the del-r command, check whether it's the closest reminder.
* Use a database. The [replit database](https://docs.replit.com/misc/database), temporarily?
