import re

from musbot.util import AUTHOR_NAME_REGEX, AUTHOR_REGEX, TITLE_REGEX, add_scheme, remove_scheme
from musbot.tracks import FORBIDDEN_CHARS_REGEX
from musbot.track_loader import TIME_REGEX
from timeit import timeit


def test():
	assert re.sub(AUTHOR_NAME_REGEX, r'\1 | \2', 'ABC - DEF - GHI') == 'ABC | DEF - GHI'
	assert re.search(AUTHOR_NAME_REGEX, 'ABC - ') is None
	assert re.search(AUTHOR_NAME_REGEX, ' - ABC') is None

	assert re.search(AUTHOR_REGEX, 'author:Kanaria,name:Brain').groups()[0] == 'Kanaria'
	assert re.search(AUTHOR_REGEX, 'name:Brain,author:Kanaria').groups()[0] == 'Kanaria'
	assert re.search(AUTHOR_REGEX, 'a:Kanaria').groups()[0] == 'Kanaria'
	assert re.search(AUTHOR_REGEX, 'a : Kanaria , smth : ...').groups()[0] == 'Kanaria'
	assert re.search(AUTHOR_REGEX, 'author : "string: with: colons"').groups()[0] == '"string: with: colons"'
	assert re.search(AUTHOR_REGEX, 'a:"string: with: colons"').groups()[0] == '"string: with: colons"'

	assert re.search(TITLE_REGEX, 'author:Kanaria,name:Brain').groups()[0] == 'Brain'
	assert re.search(TITLE_REGEX, 'title:Brain,author:Kanaria').groups()[0] == 'Brain'
	assert re.search(TITLE_REGEX, 'n:Brain').groups()[0] == 'Brain'

	assert re.search(TITLE_REGEX, 'author:Kanaria,\n\t\r name:Brain').groups()[0] == 'Brain'
	assert re.search(TITLE_REGEX, 'name:\n Brain \t').groups()[0] == 'Brain'
	assert re.search(TITLE_REGEX, 'name: "Brain" \t').groups()[0] == '"Brain"'
	assert re.search(TITLE_REGEX, 'name: "Brain \t"').groups()[0] == '"Brain \t"'


	MATCHING = '\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f\\/:*?<>"'
	NOT_MATCHING = ' !#$%&\'()+,-.0123456789;=@ABCDEFGHIJKLMNOPQRSTUVWXYZ[]^_`abcdefghijklmnopqrstuvwxyz{}~\x7f'

	assert re.sub(FORBIDDEN_CHARS_REGEX, '', MATCHING) == ''
	assert re.search(FORBIDDEN_CHARS_REGEX, NOT_MATCHING) is None


	assert add_scheme('host/path?k=v')         == 'https://host/path?k=v'
	assert add_scheme('https://host/path?k=v') == 'https://host/path?k=v'
	assert add_scheme('ftp://host/path?k=v')   == 'ftp://host/path?k=v'
	assert add_scheme('gg://host/path?k=v')    == 'gg://host/path?k=v'

	assert remove_scheme('host/path?k=v')         == 'host/path?k=v'
	assert remove_scheme('https://host/path?k=v') == 'host/path?k=v'
	assert remove_scheme('ftp://host/path?k=v')   == 'host/path?k=v'
	assert remove_scheme('gg://host/path?k=v')    == 'host/path?k=v'

def time_command_regex():
	COMMAND_REGEX = re.compile(r'^/\w+\s*')
	str1 = 'Kanaria - Brain' * 100
	str2 = '/list' + str1
	str3 = '/' + 'a' * 500
	
	def replace_command_1():
		re.sub(COMMAND_REGEX, '', str1)
	
	def replace_command_2():
		re.sub(COMMAND_REGEX, '', str2)
	
	def replace_command_3():
		re.sub(COMMAND_REGEX, '', str3)
	
	time1 = timeit(replace_command_1, number=50000)
	time2 = timeit(replace_command_2, number=50000)
	time3 = timeit(replace_command_3, number=50000)
	
	print(f'{time1:.3f}s, {time2:.3f}s, {time3:.3f}s: {(time2 - time1) / time1 * 100 :.1f}%, {(time3 - time1) / time1 * 100 :.1f}%')


def test_time_regex():
	match = re.search(TIME_REGEX, '01:30')
	assert match.group(1) == '01'
	assert match.group(2) == '30'

	match = re.search(TIME_REGEX, '01:30:59')
	assert match.group(1) == '01'
	assert match.group(2) == '30'
	assert match.group(3) == '59'

	match = re.search(TIME_REGEX, '01 : 30')
	assert match is None

	match = re.search(TIME_REGEX, '85:30')
	assert match is None

	match = re.search(TIME_REGEX, '0:0')
	assert match.group(1) == '0'
	assert match.group(2) == '0'


if __name__ == '__main__':
	test()
	test_time_regex()
	# time_command_regex()

	print('SUCCESS')
