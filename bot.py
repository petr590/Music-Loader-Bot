#!/bin/python3
import os
import sys
import re
import logging

from telebot import TeleBot, types
from typing import Dict, Optional

import database

from setup import setup
from tracks import Track, TrackPool, button_events
from track_loader import load_tracks
from track_processor import process_track
from util import get_request_title_and_author, wrap_try_except


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

	<b>Список треков</b>
	Команда /list выводит все скачанные треки. Ей можно передать строку в таком же формате, как и для поиска. При клике на трек можно изменить автора или название или удалить трек из базы.
'''.replace('\t', '')


class UserState:
	disable_filter: bool
	current_track: Optional[Track]
	current_action: Optional[dict]

	def __init__(self) -> None:
		self.disable_filter = False
		self.current_track = None
		self.current_action = None


def main() -> None:
	setup()
	database.init()

	ADMIN_ID = int(os.environ.get('ADMIN_ID'))
	bot = TeleBot(os.environ.get('BOT_TOKEN'))
	
	# Ключ: id чата, значение: состояние юзера
	user_states: Dict[int, UserState] = {}

	assert bool(UserState()) == True

	def get_state(user_id: int) -> UserState:
		state = user_states.get(user_id)
		if state is not None:
			return state
		
		state = user_states[user_id] = UserState()
		return state

	# -------------------------------------------------- Commands --------------------------------------------------

	@bot.message_handler(commands=['start', 'help'])
	@wrap_try_except(bot)
	def help(message: types.Message) -> None:
		bot.send_message(message.chat.id, HELP_MESSAGE, parse_mode='HTML')


	@bot.message_handler(commands=['stop'])
	@wrap_try_except(bot)
	def stop(message: types.Message):
		if message.from_user.id == ADMIN_ID:
			database.cleanup()
			sys.exit(0)

	@bot.message_handler(commands=['filteron'])
	@wrap_try_except(bot)
	def filter_on(message: types.Message):
		get_state(message.from_user.id).disable_filter = False
		bot.send_message(message.chat.id, 'Фильтр включен')


	@bot.message_handler(commands=['filteroff'])
	@wrap_try_except(bot)
	def filter_off(message: types.Message):
		get_state(message.from_user.id).disable_filter = True
		bot.send_message(message.chat.id, 'Фильтр отключен')


	# -------------------------------------------------- /list --------------------------------------------------

	COMMAND_REGEX = re.compile(r'^/list\s*')

	def edit_author(track: Track, message: types.Message):
		track.author = message.text
		database.update_track(track)
		return 'Трек изменён'

	
	def edit_title(track: Track, message: types.Message):
		track.title = message.text
		database.update_track(track)
		return 'Трек изменён'
	
	def download(track: Track, message: types.Message):
		process_track(track, bot, message.chat.id)
	
	def delete(track: Track, message: types.Message):
		if message.text.lower() == 'да':
			database.delete_track(track)
			return 'Трек удалён'
		else:
			return 'Отмена'
	

	EDIT_AUTHOR = {
		'button_message': 'Изменить автора',
		'begin_message': 'Введите нового автора трека',
		'keyboard': types.ReplyKeyboardRemove(),
		'callback': edit_author,
	}

	EDIT_TITLE = {
		'button_message': 'Изменить название',
		'begin_message': 'Введите новое название трека',
		'keyboard': types.ReplyKeyboardRemove(),
		'callback': edit_title,
	}

	DOWNLOAD = {
		'button_message': 'Скачать',
		'callback': download,
	}

	DELETE = {
		'button_message': 'Удалить',
		'begin_message': 'Вы уверены?',
		
		'keyboard': types.ReplyKeyboardMarkup(resize_keyboard=True).add(
			types.KeyboardButton('Да'),
			types.KeyboardButton('Нет'),
		),

		'callback': delete,
	}

	ACTION_BY_BUTTON_MESSAGE = {
		EDIT_AUTHOR['button_message']: EDIT_AUTHOR,
		EDIT_TITLE ['button_message']: EDIT_TITLE,
		DOWNLOAD   ['button_message']: DOWNLOAD,
		DELETE     ['button_message']: DELETE,
	}


	@bot.message_handler(commands=['list'])
	@wrap_try_except(bot)
	def track_list(message: types.Message):
		if message.text is None or message.text == '': return
		
		_, title, author = get_request_title_and_author(re.sub(COMMAND_REGEX, '', message.text))

		pool = TrackPool(handle_track_click, database.get_track_list(message.from_user.id, title, author))
		pool.print_next(bot, message.chat.id)
	

	def handle_track_click(track: Track, bot: TeleBot, chat_id: int, user_id: int):
		keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)

		keyboard.add(
			*[types.KeyboardButton(msg) for msg in ACTION_BY_BUTTON_MESSAGE.keys()],
			row_width=2
		)


		bot.send_message(chat_id, 'Что вы хотите сделать с треком?', reply_markup=keyboard)
		get_state(user_id).current_track = track
	

	def text_filter(message: types.Message):
		return get_state(message.from_user.id).current_track is not None\
			and message.text in ACTION_BY_BUTTON_MESSAGE


	def action_filter(message: types.Message):
		state = get_state(message.from_user.id)
		return state.current_track is not None and state.current_action is not None


	@bot.message_handler(func=text_filter)
	@wrap_try_except(bot)
	def begin_action(message: types.Message):
		action = ACTION_BY_BUTTON_MESSAGE[message.text]
		state = get_state(message.from_user.id)

		if 'begin_message' in action:
			state.current_action = action
			bot.send_message(message.chat.id, action['begin_message'], reply_markup=action['keyboard'])
		else:
			action['callback'](state.current_track, message)
			state.current_track = None
	

	@bot.message_handler(func=action_filter)
	@wrap_try_except(bot)
	def do_action(message: types.Message):
		state = get_state(message.from_user.id)
		end_message = state.current_action['callback'](state.current_track, message)

		state.current_track = None
		state.current_action = None
		
		bot.send_message(message.chat.id, end_message, reply_markup=types.ReplyKeyboardRemove())



	# -------------------------------------------------- messages --------------------------------------------------


	@bot.message_handler()
	@wrap_try_except(bot)
	def handle_message(message: types.Message) -> None:
		if message.text is None or message.text == '': return

		database.add_or_update_user(message.from_user)
		
		request, title, author = get_request_title_and_author(message.text)
		
		if get_state(message.from_user.id).disable_filter:
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
