#!/bin/python3
import os
import sys
import re
import logging
import atexit

from telebot import TeleBot, types
from typing import Dict

from musbot import setup, database
from musbot.tracks import Track, TrackPool, button_events
from musbot.track_loader import load_tracks
from musbot.track_processor import send_track, download_process_and_send_track
from musbot.actions import Action, ChooseAction, NO_ACTION, ACTION_BY_BUTTON_MESSAGE
from musbot.util import get_request_title_and_author, wrap_try_except, format_last_ex_info


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
	database.init()

	ADMIN_ID = int(os.environ.get('ADMIN_ID'))
	ADMIN_PWD = os.environ.get('ADMIN_PWD')
	bot = TeleBot(os.environ.get('BOT_TOKEN'))
	

	# ----------------------------------------- Commands ------------------------------------------

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
	def filteron(message: types.Message):
		UserState.get(message.from_user.id).disable_filter = False
		bot.send_message(message.chat.id, 'Фильтр включен')


	@bot.message_handler(commands=['filteroff'])
	@wrap_try_except(bot)
	def filteroff(message: types.Message):
		UserState.get(message.from_user.id).disable_filter = True
		bot.send_message(message.chat.id, 'Фильтр отключен')
	

	@bot.message_handler(commands=['cancel'])
	@wrap_try_except(bot)
	def cancel(message: types.Message):
		UserState.get(message.from_user.id).current_action = NO_ACTION
		bot.send_message(message.chat.id, 'Отменено', reply_markup=types.ReplyKeyboardRemove())


	# -------------------------------------- Hidden commands --------------------------------------
	
	@bot.message_handler(commands=['diag'])
	@wrap_try_except(bot)
	def diagnostics(message: types.Message):
		trace = format_last_ex_info()

		bot.send_message(
			message.chat.id,
			f'```\n{trace}\n```' if trace else 'Ошибок нет',
			parse_mode='MarkdownV2'
		)


	pwd_request = False

	def is_admin(message: types.Message):
		return message.from_user.id == ADMIN_ID

	@bot.message_handler(commands=['shutdown'], func=is_admin)
	@wrap_try_except(bot)
	def shutdown(message: types.Message):
		nonlocal pwd_request
		pwd_request = True
		bot.send_message(message.chat.id, 'Подтвердите пароль')
	
	@bot.message_handler(func=lambda message: pwd_request and is_admin(message))
	@wrap_try_except(bot)
	def handle_admin_pwd(message: types.Message):
		nonlocal pwd_request
		pwd_request = False

		if message.text == ADMIN_PWD:
			bot.send_message(message.chat.id, 'Выключение...')
			database.cleanup()
			os.system("systemctl poweroff")
			sys.exit(0)
		else:
			bot.send_message(message.chat.id, 'Пароль неверен')


	# ------------------------------------------- /list -------------------------------------------
	
	COMMAND_REGEX = re.compile(r'^/\w+\s*')


	@bot.message_handler(commands=['list'])
	@wrap_try_except(bot)
	def track_list(message: types.Message):
		_, title, author = get_request_title_and_author(re.sub(COMMAND_REGEX, '', message.text))
		user_id = message.from_user.id

		tracks = database.get_track_list(user_id, title, author)
		pool = TrackPool(user_id=user_id, tracks=tracks, callback=change_track)
		pool.print(bot, message.chat.id)
	

	# Вызывается при клике на кнопку с треком
	def change_track(track: Track, bot: TeleBot, chat_id: int, user_id: int):
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


	# ----------------------------------------- messages ------------------------------------------


	@bot.message_handler()
	@wrap_try_except(bot)
	def handle_message(message: types.Message) -> None:
		database.add_or_update_user(message.from_user)
		
		request, title, author = get_request_title_and_author(message.text)
		user_id = message.from_user.id
		
		if UserState.get(user_id).disable_filter:
			title = None
			author = None
		
		tracks = load_tracks(request, title, author)
		database.set_ids(user_id, tracks)

		pool = TrackPool(user_id=user_id, tracks=tracks, callback=on_track_clicked)
		pool.print(bot, message.chat.id)


	def on_track_clicked(track: Track, bot: TeleBot, chat_id: int, user_id: int):
		if track.id is None:
			track.id = database.add_or_update_track(user_id, track)
			download_process_and_send_track(track, bot, chat_id)
		else:
			database.add_or_update_track(user_id, track)
			change_track(track, bot, chat_id, user_id)
	

	# maybe TODO
	
	# @bot.message_handler(content_types=['audio'])
	# def handle_audio(message: types.Message) -> None:
	# 	audio = message.audio
	# 	chat_id = message.chat.id
	# 	user_id = message.from_user.id

	# 	track = Track(url=None, title=audio.title, author=audio.performer, duration=audio.duration)

	# 	if track.author is None:
	# 		bot.send_message(chat_id, 'Введите автора трека')
	# 		UserState.get(user_id).current_action = SetAuthorAction(track)

	# 	if track.title is None:
	# 		bot.send_message(chat_id, 'Введите название трека')
	# 		UserState.get(user_id).current_action = SetTitleAction(track)


	@bot.callback_query_handler(func=lambda _: True)
	@wrap_try_except(bot)
	def handle_callback(query: types.CallbackQuery) -> None:
		chat_id = query.message.chat.id
		handler = button_events.get(query.data)

		if handler is not None:
			handler(bot, chat_id, query.from_user.id)


	# ------------------------------------------- start -------------------------------------------
 
	TrackPool.init(database.deserialize_track_pools([change_track, on_track_clicked]))
 
	def cleanup():
		database.serialize_track_pools(TrackPool.get_track_pools())
		database.cleanup()

	atexit.register(cleanup)
 
	logger = logging.getLogger('root')
	logger.info('Bot successfully started')

	bot.infinity_polling()
	


if __name__ == '__main__':
	main()
