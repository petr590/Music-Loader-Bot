#!/bin/python3
import os
import re
import dotenv
import traceback

from telebot import TeleBot, types
from typing import List, Dict, Tuple, Optional
from tracks import Track, load_tracks
from file_processor import process


def init_dotenv():
	path = os.path.join(os.path.dirname(__file__), '.env')

	if os.path.exists(path):
		dotenv.load_dotenv(path)


# Определяет формат '<author> - <name>', возвращает <author> в \1, <name> в \2
AUTHOR_NAME_REGEX = re.compile(r'^(.+?)[ \t]+[-−–—][ \t]+(.+)$')

# Определяет текст в кавычках или до ближайшего двоеточия
VALUE_PATTERN = r'("[^"]+"|[^:"]+?)(?=$|,\s*[a-z]+\s*:)'

# Ищет автора, возвращает его в \1
AUTHOR_REGEX = re.compile(rf'\b(?:author|a)\s*:\s*{VALUE_PATTERN}', re.I)

# Ищет название, возвращает его в \1
NAME_REGEX = re.compile(rf'\b(?:name|n|title|t)\s*:\s*{VALUE_PATTERN}', re.I)


def get_request_author_and_name(text: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
	""" Возвращает запрос, автора и назнание по сообщению пользователя """

	match = re.search(AUTHOR_NAME_REGEX, text)
	if match:
		author = match.group(1)
		name = match.group(2)
	else:
		match = re.search(AUTHOR_REGEX, text)
		author = match.group(1) if match else None

		match = re.search(NAME_REGEX, text)
		name = match.group(1) if match else None
	
	if author is None and name is None:
		author = text
	

	if author is not None and name is not None:
		request = f'{author} {name}'
	else:
		request = author if author != None else name
	
	return request, author, name


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
			msg = bot.send_message(chat_id, f'Найдено {len(self.tracks)} треков', reply_markup=markup)
			self.message_id = msg.id
		else:
			bot.edit_message_reply_markup(chat_id, self.message_id, reply_markup=markup)
	

	@property
	def key_show_more(self):
		return str(id(self)) + '_show_more'


track_pools: Dict[int, TrackPool] = {}

def handle_message(message: types.Message, bot: TeleBot):
	if message.text is None or message.text == '':
		return

	pool = TrackPool(load_tracks(*get_request_author_and_name(message.text)))
	pool.print_next(bot, message.chat.id)

	track_pools[message.chat.id] = pool


def handle_callback(query: types.CallbackQuery, bot: TeleBot):
	chat_id = query.message.chat.id

	if chat_id in track_pools and query.data == track_pools[chat_id].key_show_more:
		track_pools[chat_id].print_next(bot, chat_id)
		return

	if not query.data.isdigit():
		return
	
	track = Track.get_cached(int(query.data))
	if track is None:
		return

	try:
		process(track, bot, chat_id)
	except:
		traceback.print_exc()
		bot.send_message(chat_id, 'Ошибка при обработке файла')


def help(message: types.Message, bot: TeleBot):
	bot.send_message(message.chat.id,
		'''
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
		''',
		parse_mode='HTML'
	)


def main() -> None:
	init_dotenv()
	
	bot = TeleBot(os.environ.get('BOT_TOKEN'))
	
	bot.message_handler(pass_bot=True, commands=['help'])(help)
	bot.message_handler(pass_bot=True, content_types=['text'])(handle_message)
	bot.callback_query_handler(pass_bot=True, func=lambda _: True)(handle_callback)

	bot.infinity_polling()


if __name__ == '__main__':
	main()