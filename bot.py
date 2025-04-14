#!/bin/python3
import os
import sys
import re
import traceback
import logging

from telebot import TeleBot, types
from typing import List, Dict, Tuple, Optional, Callable, TypeVar

import database

from setup import setup
from tracks import Track, load_tracks
from file_processor import process
from util import word_form_by_num


# Определяет формат '<author> - <name>', возвращает <author> в \1, <name> в \2
AUTHOR_NAME_REGEX = re.compile(r'^(.+?)[ \t]+[-−–—][ \t]+(.+)$')

# Определяет текст в кавычках или текст до ближайшего двоеточия
VALUE_PATTERN = r'("[^"]+" | [^:"]+?) \s* (?= $ | ,\s*[a-z]+\s*:)'

# Ищет автора, возвращает его в \1
AUTHOR_REGEX = re.compile(rf'\b (?:author|a) \s*:\s* {VALUE_PATTERN}', re.I | re.X)

# Ищет название, возвращает его в \1
NAME_REGEX = re.compile(rf'\b (?:name|n|title|t) \s*:\s* {VALUE_PATTERN}', re.I | re.X)


def get_request_author_and_name(text: str, request_only: bool) -> Tuple[str, Optional[str], Optional[str]]:
	"""
	Возвращает запрос, автора и назнание по сообщению пользователя
	@param request_only - если True, то возвращает только запрос, а имя и название равны None
	"""

	match = re.search(AUTHOR_NAME_REGEX, text)
	if match:
		author = match.group(1)
		name = match.group(2)
	else:
		match = re.search(AUTHOR_REGEX, text)
		author = match.group(1).strip('"') if match else None

		match = re.search(NAME_REGEX, text)
		name = match.group(1).strip('"') if match else None
	
	if author is None and name is None:
		author = text
	

	if author is not None and name is not None:
		request = f'{author} {name}'
	else:
		request = author if author != None else name
	
	return (request, None, None) if request_only else (request, author, name)


# Размер одной страницы при выводе списка треков
PAGE_SIZE = 10

class TrackPool:
	""" Хранит список треков и номер последнего трека, показанного пользователю """

	def __init__(self, tracks: List[Track]):
		self.tracks = tracks
		self.last_index = 0
		self.message_id: Optional[int] = None
	

	def print_next(self, bot: TeleBot, chat_id: int):
		""" Выводит следующую группу треков, а также кнопку для вывода следующей группы, если необходимо """

		markup = types.InlineKeyboardMarkup()
		next_index = min(self.last_index + PAGE_SIZE, len(self.tracks))

		for i in range(next_index):
			track = self.tracks[i]
			markup.add(types.InlineKeyboardButton(track.get_text(), callback_data=str(track.id)))
		
		if next_index < len(self.tracks):
			next_count = min(PAGE_SIZE, len(self.tracks) - next_index)
			markup.add(types.InlineKeyboardButton(f'Показать ещё {next_count}', callback_data=self.key_show_more))

		self.last_index = next_index
		
		if self.message_id is None:
			tracks_count = len(self.tracks)
			
			msg = word_form_by_num(tracks_count,
					f'Найден {tracks_count} трек',
					f'Найдены {tracks_count} трека',
					f'Найдено {tracks_count} треков'
			)

			self.message_id = bot.send_message(chat_id, msg, reply_markup=markup).id
		else:
			bot.edit_message_reply_markup(chat_id, self.message_id, reply_markup=markup)
	

	@property
	def key_show_more(self):
		return str(id(self)) + '_show_more'


T = TypeVar('T')

def try_except(bot: TeleBot, chat_id: int, func: Callable[[], T]) -> Optional[T]:
	try:
		return func()
	except:
		traceback.print_exc()
		bot.send_message(chat_id, 'Ошибка')
		return None


track_pools: Dict[int, TrackPool] = {}
disable_filter: Dict[int, bool] = {}

def handle_message(message: types.Message, bot: TeleBot) -> None:
	if message.text is None or message.text == '':
		return

	chat_id = message.chat.id
	try_except(bot, chat_id, lambda: database.add_or_update_user(message.from_user))

	data = try_except(bot, chat_id, lambda: get_request_author_and_name(message.text, disable_filter.get(chat_id, False)))
	if data is None:
		return

	pool = TrackPool(load_tracks(*data))
	pool.print_next(bot, chat_id)
	track_pools[chat_id] = pool


def handle_callback(query: types.CallbackQuery, bot: TeleBot) -> None:
	chat_id = query.message.chat.id

	if chat_id in track_pools and query.data == track_pools[chat_id].key_show_more:
		track_pools[chat_id].print_next(bot, chat_id)
		return

	if not query.data.isdigit():
		return
	
	track = Track.get_cached(int(query.data))
	if track is None:
		return

	try_except(bot, chat_id, lambda: process(track, bot, chat_id))
	try_except(bot, chat_id, lambda: database.add_track_info(query.from_user.id, track))


def main() -> None:
	setup()
	database.init()

	ADMIN_ID = int(os.environ.get('ADMIN_ID'))
	bot = TeleBot(os.environ.get('BOT_TOKEN'))

	HELP_MESSAGE = '''
			Music Loader - бот для скачивания музыки с сайтов.
			<b>Поддерживаемые сайты:</b>
			- www.ligaudio.ru
			- rus.hitmotop.com

			<b>Поиск</b>
			Данный бот принимает три формата названия для поиска музыки:
			- <b><u>&lt;автор&gt;</u></b> - выполняет поиск по автору.
			- <b><u>&lt;автор&gt; - &lt;название&gt;</u></b> - выполняет поиск по автору и названию.
			- <b><u>author:&lt;автор&gt;, title:&lt;название&gt;</u></b> - выполняет поиск по автору и названию. Вы можете заменить <b><u>author:</u></b> на <b><u>a:</u></b>, а <b><u>title:</u></b> на <b><u>name:</u></b>, <b><u>t:</u></b> или <b><u>n:</u></b>. Вы также можете указать только автора или название.

			При поиске регистр не учитывается.

			<b>Примеры:</b>
			- <b><u>Kanaria</u></b> - ищет все песни исполнителя Kanaria
			- <b><u>kanaria - identity</u></b> - ищет песню Identity исполнителя Kanaria
			- <b><u>author: kanaria, title: identity</u></b> - то же самое
			- <b><u>t:identity, a:kanaria</u></b> - то же самое
			- <b><u>title: "name:with:colons"</u></b> - ищет песню с названием name:with:colons, кавычки в данном случае обязательны.

			<b>Фильтр</b>
			Фильтр дополнительно фильтрует результат поиска сайтов, так как они могут выдавать много лишних результатов. Фильтр можно включить и отключить командами /filteron и  /filteroff. По умолчанию он включен.
			'''.replace('\t\t\t', '')
	
	@bot.message_handler(commands=['start', 'help'])
	def help(message: types.Message) -> None:
		bot.send_message(message.chat.id, HELP_MESSAGE, parse_mode='HTML')


	@bot.message_handler(commands=['stop'])
	def stop(message: types.Message):
		if message.from_user.id == ADMIN_ID:
			database.cleanup()
			sys.exit(0)


	@bot.message_handler(commands=['filteron'])
	def filter_on(message: types.Message):
		disable_filter[message.chat.id] = False
		bot.send_message(message.chat.id, 'Фильтр включен')


	@bot.message_handler(commands=['filteroff'])
	def filter_off(message: types.Message):
		disable_filter[message.chat.id] = True
		bot.send_message(message.chat.id, 'Фильтр отключен')


	bot.message_handler(pass_bot=True, content_types=['text'])(handle_message)
	bot.callback_query_handler(pass_bot=True, func=lambda _: True)(handle_callback)


	logger = logging.getLogger('root')
	logger.info('Bot successfully started')

	bot.infinity_polling()

	database.cleanup()
	


if __name__ == '__main__':
	main()