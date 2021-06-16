class Task(object):
    '''A task to be done at a specific time'''
    def __init__(self, task_type: str, author_id: int, start_time: str, target_time: str, duration: str = '', is_dm: bool = True, guild_id: int = 0, channel_id: int = 0):
        '''Create a Task
        
        The time strings must be in Python's default ISO format
        (with no spaces). The duration string is for output
        only and can be in any format without commas.'''
        self.task_type = task_type
        self.author_id = author_id
        self.start_time = start_time
        self.target_time = target_time
        self.duration = duration
        self.is_dm = is_dm
        self.guild_id = guild_id
        self.channel_id = channel_id

    async def get_task_key(self):
        return f'task:{self.task_type} {self.author_id} {self.target_time}'

    async def get_destination(self, bot):
        if self.is_dm:
            return await bot.fetch_user(self.author_id)
        else:
            guild = bot.get_guild(self.guild_id)
            return guild.get_channel(self.channel_id)


class Reminder(Task):
    def __init__(self, message: str, author_id: int, start_time: str, target_time: str, duration: str = '', is_dm: bool = True, guild_id: int = 0, channel_id: int = 0):
        super().__init__('reminder', author_id, start_time, target_time, duration, is_dm, guild_id, channel_id)
        self.message = message

    def __repr__(self):
        return f'Reminder("{self.message}", {self.author_id}, "{self.start_time}", "{self.target_time}", "{self.duration}", "{self.is_dm}", {self.guild_id}, {self.channel_id})'

    def __eq__(self, other):
        return self.message == other.message \
            and self.author_id == other.author_id \
            and self.start_time == other.start_time \
            and self.target_time == other.target_time \
            and self.duration == other.duration \
            and self.is_dm == other.is_dm \
            and self.guild_id == other.guild_id \
            and self.channel_id == other.channel_id

    def __ne__(self, other):
        return self.message != other.message \
            or self.author_id != other.author_id \
            or self.start_time != other.start_time \
            or self.target_time != other.target_time \
            or self.duration != other.duration \
            or self.is_dm != other.is_dm \
            or self.guild_id != other.guild_id \
            or self.channel_id != other.channel_id


class Daily_Quote(Task):
    def __init__(self, author_id: int, start_time: str, target_time: str, duration: str = '', is_dm: bool = True, guild_id: int = 0, channel_id: int = 0):
        super().__init__('daily_quote', author_id, start_time, target_time, duration, is_dm, guild_id, channel_id)

    def __repr__(self):
        return f'Daily_Quote({self.author_id}, "{self.start_time}", "{self.target_time}", "{self.duration}", "{self.is_dm}", {self.guild_id}, {self.channel_id})'
