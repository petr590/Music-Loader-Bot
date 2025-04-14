import re

from bot import AUTHOR_NAME_REGEX, AUTHOR_REGEX, NAME_REGEX
from tracks import FORBIDDEN_CHARS

if __name__ == '__main__':
	assert re.sub(AUTHOR_NAME_REGEX, r'\1 | \2', 'ABC - DEF - GHI') == 'ABC | DEF - GHI'
	assert re.search(AUTHOR_NAME_REGEX, 'ABC - ') is None
	assert re.search(AUTHOR_NAME_REGEX, ' - ABC') is None

	assert re.search(AUTHOR_REGEX, 'author:Kanaria,name:Brain').groups()[0] == 'Kanaria'
	assert re.search(AUTHOR_REGEX, 'name:Brain,author:Kanaria').groups()[0] == 'Kanaria'
	assert re.search(AUTHOR_REGEX, 'a:Kanaria').groups()[0] == 'Kanaria'
	assert re.search(AUTHOR_REGEX, 'a : Kanaria , smth : ...').groups()[0] == 'Kanaria'
	assert re.search(AUTHOR_REGEX, 'author : "string: with: colons"').groups()[0] == '"string: with: colons"'
	assert re.search(AUTHOR_REGEX, 'a:"string: with: colons"').groups()[0] == '"string: with: colons"'

	assert re.search(NAME_REGEX, 'author:Kanaria,name:Brain').groups()[0] == 'Brain'
	assert re.search(NAME_REGEX, 'title:Brain,author:Kanaria').groups()[0] == 'Brain'
	assert re.search(NAME_REGEX, 'n:Brain').groups()[0] == 'Brain'

	assert re.search(NAME_REGEX, 'author:Kanaria,\n\t\r name:Brain').groups()[0] == 'Brain'
	assert re.search(NAME_REGEX, 'name:\n Brain \t').groups()[0] == 'Brain'
	assert re.search(NAME_REGEX, 'name: "Brain" \t').groups()[0] == '"Brain"'
	assert re.search(NAME_REGEX, 'name: "Brain \t"').groups()[0] == '"Brain \t"'


	MATCHING = '\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f\\/:*?<>"'
	NOT_MATCHING = ' !#$%&\'()+,-.0123456789;=@ABCDEFGHIJKLMNOPQRSTUVWXYZ[]^_`abcdefghijklmnopqrstuvwxyz{}~\x7f'

	assert re.sub(FORBIDDEN_CHARS, '', MATCHING) == ''
	assert re.search(FORBIDDEN_CHARS, NOT_MATCHING) is None

	print('SUCCESS')