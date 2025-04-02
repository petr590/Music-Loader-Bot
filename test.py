import re
from bot import AUTHOR_NAME_REGEX, AUTHOR_REGEX, NAME_REGEX

if __name__ == '__main__':
	assert re.sub(AUTHOR_NAME_REGEX, r'\1 | \2', 'ABC - DEF - GHI') == 'ABC | DEF - GHI'
	assert re.search(AUTHOR_NAME_REGEX, 'ABC - ') is None
	assert re.search(AUTHOR_NAME_REGEX, ' - ABC') is None

	assert re.search(AUTHOR_REGEX, 'author:Kanaria,name:Brain').groups()[0] == 'Kanaria'
	assert re.search(AUTHOR_REGEX, 'name:Brain,author:Kanaria').groups()[0] == 'Kanaria'
	assert re.search(AUTHOR_REGEX, 'a:Kanaria').groups()[0] == 'Kanaria'
	assert re.search(AUTHOR_REGEX, 'a : Kanaria , smth : ...').groups()[0] == 'Kanaria '
	assert re.search(AUTHOR_REGEX, 'author : "string: with: colons"').groups()[0] == '"string: with: colons"'
	assert re.search(AUTHOR_REGEX, 'a:"string: with: colons"').groups()[0] == '"string: with: colons"'