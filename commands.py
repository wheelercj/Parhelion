import random


def echo(string):
	"""echo the input."""
	return string


# def remind(string):
# 	"""get a text-to-speech reminder message after x minutes (default: 15)."""
# 	args = string.split()
# 	if not len(args):
# 		return
# 	if args[0].isnumeric() and len(args) > 1:
# 		# TODO: wait args[0] minutes
# 	else:
# 		# TODO: wait 15 minutes

# 		return '/tts ' + string.split(' ', 1)[1]
# 		# TODO: also mention the person who used this command.


def roll(string):
	"""roll a die. Optionally specify lowest and highest possible numbers (defaults are 1 and 6)."""
	bounds = string.split()
	
	low = 1
	high = 6
	if len(bounds) > 0:
		low = int(bounds[0])
	if len(bounds) > 1:
		high = int(bounds[1])

	if  low <= high:
		return str(random.randint(low, high))
	else:
		return f'{low} > {high}'


def flip_coin(_):
	"""flip a coin."""
	n = random.randint(1, 2)
	if n == 1:
		return 'heads'
	else:
		return 'tails'


def reverse(string):
	"""reverse the input."""
	return string[::-1]


def rot13(string):
	"""rotate each letter 13 letters through the alphabet."""
	string = string.lower()
	new_string = ''
	alphabet = 'abcdefghijklmnopqrstuvwxyz'
	for char in string:
		index = alphabet.find(char)
		if index != -1:
			new_index = (index + 13) % 26
			new_string += alphabet[new_index]
		else:
			new_string += char

	return new_string
