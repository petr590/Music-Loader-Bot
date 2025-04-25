import re
import time
import logging

from telebot import TeleBot, types
from typing import TypeVar, Callable, Tuple, Optional, Union

logger = logging.getLogger('root')
T = TypeVar('T')

HEADERS = {
	'Accept': 'text/html',
	'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 12_3_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.4 Safari/605.1.15',
}

class Timer:
	def __init__(self) -> None:
		self.__start = None
	
	def start(self) -> 'Timer':
		self.__start = time.time()
		return self
	
	def stop(self, message: str) -> None:
		end = time.time()

		if self.__start is None:
			raise ValueError('Timer is not started')

		logger.debug(f'{message}: {end - self.__start} sec')
		self.__start = None
	
	def run(self, message: str, func: Callable[[], T]) -> T:
		self.start()
		result = func()
		self.stop(message)
		return result


def word_form_by_num(num: int, word_1: str, word_2_4: str, word_many: str) -> str:
	""" Возвращает форму слова в зависимости от числа """

	ones = num % 10
	tens = num % 100 // 10

	if tens == 1: return word_many
	if ones == 1: return word_1
	if 2 <= ones <= 4: return word_2_4
	return word_many


# Определяет формат '<author> - <name>', возвращает <author> в \1, <name> в \2
AUTHOR_NAME_REGEX = re.compile(r'^(.+?)[ \t]+[-−–—][ \t]+(.+)$')

# Определяет текст в кавычках или текст до ближайшего двоеточия
VALUE_PATTERN = r'("[^"]+" | [^:"]+?) \s* (?= $ | ,\s*[a-z]+\s*:)'

# Ищет автора, возвращает его в \1
AUTHOR_REGEX = re.compile(rf'\b (?:author|a) \s*:\s* {VALUE_PATTERN}', re.I | re.X)

# Ищет название, возвращает его в \1
TITLE_REGEX = re.compile(rf'\b (?:name|n|title|t) \s*:\s* {VALUE_PATTERN}', re.I | re.X)


def get_request_title_and_author(text: str) -> Tuple[str, Optional[str], Optional[str]]:
	""" Возвращает запрос, назнание и автора по сообщению пользователя """

	match = re.search(AUTHOR_NAME_REGEX, text)
	if match:
		author = match.group(1)
		title = match.group(2)
	else:
		match = re.search(AUTHOR_REGEX, text)
		author = match.group(1).strip('"') if match else None

		match = re.search(TITLE_REGEX, text)
		title = match.group(1).strip('"') if match else None
	
	if author is None and title is None:
		author = text
	

	if author is not None and title is not None:
		request = f'{author} {title}'
	else:
		request = author if author != None else title
	
	return request, title, author


MsgOrQuery = Union[types.Message, types.CallbackQuery]
Handler = Callable[[MsgOrQuery], None]

def wrap_try_except(bot: TeleBot) -> Callable[[Handler], Handler]:
	"""
	Возвращает декоратр, который оборачивает вызов функции в try - except.
	При исключении пишет пользователю сообщение 'Ошибка' и выводит стектрейс об ошибке.
	"""

	def decorator(func: Handler) -> Handler:
		def wrapper(arg1: MsgOrQuery) -> None:
			try:
				func(arg1)
			except Exception as ex:
				if isinstance(arg1, types.Message):
					chat_id = arg1.chat.id
				else:
					chat_id = arg1.message.chat.id
				
				logger.error(type(ex), exc_info=ex)
				bot.send_message(chat_id, 'Ошибка')
		
		return wrapper
	return decorator


SCHEME_REGEX = re.compile(r'^\w+://', re.I)

def remove_scheme(url: str) -> str:
	""" Удаляет схему из url """
	return re.sub(SCHEME_REGEX, '', url)

def add_scheme(url: str) -> str:
	""" Добавляет схему https:// в url, если её нет """
	return url if re.match(SCHEME_REGEX, url) else 'https://' + url