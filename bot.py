#!/bin/python3
import os
import sys
import re
import logging

from telebot import TeleBot, types
from typing import Dict

from musbot import database
from musbot.setup import setup
from musbot.tracks import Track, TrackPool, button_events
from musbot.track_loader import load_tracks
from musbot.track_processor import process_track
from musbot.actions import Action, ChooseAction, NO_ACTION, ACTION_BY_BUTTON_MESSAGE
from musbot.util import get_request_title_and_author, wrap_try_except


START_MESSAGE = '''
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

	<b>Список треков</b>
	Команда /list выводит все скачанные треки. Ей можно передать строку в таком же формате, как и для поиска. При клике на трек можно изменить автора, название или удалить трек из базы.
'''.replace('\t', '')


class UserState:
	""" Состояние юзера. Хранит настройки и текущее действие. """
	
	# Ключ: id чата, значение: состояние юзера
	_states: Dict[int, 'UserState'] = {}
	
	disable_filter: bool
	current_action: Action

	def __init__(self) -> None:
		self.disable_filter = False
		self.current_action = NO_ACTION
	
	@staticmethod
	def get(user_id: int) -> 'UserState':
		""" Возвращает состояние юзера по его id. Если такого состояния нет, создаёт его. """
		
		state = UserState._states.get(user_id)
		if state is not None:
			return state
		
		state = UserState._states[user_id] = UserState()
		return state


def main() -> None:
	setup()
	database.init()

	ADMIN_ID = int(os.environ.get('ADMIN_ID'))
	bot = TeleBot(os.environ.get('BOT_TOKEN'))
	

	# -------------------------------------------------- Commands --------------------------------------------------

	@bot.message_handler(commands=['start'])
	@wrap_try_except(bot)
	def start(message: types.Message) -> None:
		bot.send_message(message.chat.id, START_MESSAGE, parse_mode='HTML')


	@bot.message_handler(commands=['stop'])
	@wrap_try_except(bot)
	def stop(message: types.Message):
		if message.from_user.id == ADMIN_ID:
			database.cleanup()
			sys.exit(0)

	@bot.message_handler(commands=['filteron'])
	@wrap_try_except(bot)
	def filter_on(message: types.Message):
		UserState.get(message.from_user.id).disable_filter = False
		bot.send_message(message.chat.id, 'Фильтр включен')


	@bot.message_handler(commands=['filteroff'])
	@wrap_try_except(bot)
	def filter_off(message: types.Message):
		UserState.get(message.from_user.id).disable_filter = True
		bot.send_message(message.chat.id, 'Фильтр отключен')


	# -------------------------------------------------- /list --------------------------------------------------
	
	COMMAND_REGEX = re.compile(r'^/\w+\s*')


	@bot.message_handler(commands=['list'])
	@wrap_try_except(bot)
	def track_list(message: types.Message):
		_, title, author = get_request_title_and_author(re.sub(COMMAND_REGEX, '', message.text))

		pool = TrackPool(handle_track_click, database.get_track_list(message.from_user.id, title, author))
		pool.print_next(bot, message.chat.id)
	

	# Вызывается при клике на кнопку с треком
	def handle_track_click(track: Track, bot: TeleBot, chat_id: int, user_id: int):
		keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
		keyboard.add(
			*[types.KeyboardButton(msg) for msg in ACTION_BY_BUTTON_MESSAGE],
			row_width=2
		)

		bot.send_message(chat_id, 'Что вы хотите сделать с треком?', reply_markup=keyboard)
		UserState.get(user_id).current_action = ChooseAction(track)
	

	def action_filter(message: types.Message):
		return UserState.get(message.from_user.id).current_action.filter(message)

	@bot.message_handler(func=action_filter)
	@wrap_try_except(bot)
	def handle_action(message: types.Message):
		state = UserState.get(message.from_user.id)
		state.current_action = state.current_action.handle_message(message, bot)


	# -------------------------------------------------- messages --------------------------------------------------


	@bot.message_handler()
	@wrap_try_except(bot)
	def handle_message(message: types.Message) -> None:
		database.add_or_update_user(message.from_user)
		
		request, title, author = get_request_title_and_author(message.text)
		
		if UserState.get(message.from_user.id).disable_filter:
			title = None
			author = None

		pool = TrackPool(process_track_and_save_info, load_tracks(request, title, author))
		pool.print_next(bot, message.chat.id)


	def process_track_and_save_info(track: Track, bot: TeleBot, chat_id: int, user_id: int):
		process_track(track, bot, chat_id)
		database.add_track_info(user_id, track)


	@bot.callback_query_handler(func=lambda _: True)
	@wrap_try_except(bot)
	def handle_callback(query: types.CallbackQuery) -> None:
		chat_id = query.message.chat.id
		handler = button_events.get(query.data)

		if handler is not None:
			handler(bot, chat_id, query.from_user.id)


	# -------------------------------------------------- start --------------------------------------------------

	logger = logging.getLogger('root')
	logger.info('Bot successfully started')

	bot.infinity_polling()

	database.cleanup()
	


if __name__ == '__main__':
	main()
