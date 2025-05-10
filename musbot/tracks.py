import re

from telebot import TeleBot, types
from typing import List, Dict, Optional, Callable

from .util import word_form_by_num


# Символы, запрещённые в именах файлов
FORBIDDEN_CHARS_REGEX = re.compile(r'[\\|/:*?<>"\x00-\x1F]')
FORBIDDEN_CHARS_REPL = '_'

button_events: Dict[str, Callable[[TeleBot, int, int], None]] = {}


class Track:
	def __init__(self, url: str, title: str, author: str, duration: Optional[str] = None, id: Optional[int] = None):
		self.url = url
		self.title = title
		self.author = author
		self.duration = duration
		self.id = id
	
	@property
	def key(self) -> int:
		return str(id(self))

	
	def get_text(self) -> str:
		if self.duration is not None:
			return f'{self.author}   ⸺   {self.title}   ⸺   {self.duration}'
		else:
			return f'{self.author}   ⸺   {self.title}'
	
	def get_filename(self) -> str:
		return re.sub(FORBIDDEN_CHARS_REGEX, FORBIDDEN_CHARS_REPL, f'{self.author} - {self.title}')


# Размер одной страницы при выводе списка треков
PAGE_SIZE = 10

class TrackPool:
	""" Хранит список треков и номер последнего трека, показанного пользователю """

	def __init__(self, callback: Callable[[Track, TeleBot, int, int], None], tracks: List[Track]):
		self.tracks = tracks
		self.shown_count = 0
		self.hidden = False
		self.message_id: Optional[int] = None

		for track in tracks:
			button_events[track.key] = lambda *args, _track = track: callback(_track, *args)
		
		button_events[self.key_print_next] = self.print_next

		if len(tracks) > PAGE_SIZE:
			button_events[self.key_toggle] = self.toggle
	

	def print(self, bot: TeleBot, chat_id: int):
		""" Выводит группу треков или только кнопку """

		shown_count = self.shown_count
		tracks_count = len(self.tracks)
		markup = types.InlineKeyboardMarkup()

		if tracks_count > PAGE_SIZE:
			button_msg = f'Развернуть ({shown_count})  ▼' if self.hidden else 'Свернуть  ▲'
			markup.add(types.InlineKeyboardButton(button_msg, callback_data=self.key_toggle))
		
		if not self.hidden:
			for i in range(shown_count):
				track = self.tracks[i]
				markup.add(types.InlineKeyboardButton(track.get_text(), callback_data=track.key))
			
			if shown_count < tracks_count:
				next_count = min(PAGE_SIZE, tracks_count - shown_count)
				markup.add(types.InlineKeyboardButton(f'Показать ещё {next_count}', callback_data=self.key_print_next))
			else:
				button_events.pop(self.key_print_next, None)
		

		if self.message_id is None:
			msg = word_form_by_num(tracks_count,
					f'Найден {tracks_count} трек',
					f'Найдены {tracks_count} трека',
					f'Найдено {tracks_count} треков'
			)

			self.message_id = bot.send_message(chat_id, msg, reply_markup=markup).id
		else:
			bot.edit_message_reply_markup(chat_id, self.message_id, reply_markup=markup)


	def print_next(self, bot: TeleBot, chat_id: int, *_):
		""" Выводит следующую группу треков, а также кнопку для вывода следующей группы, если необходимо """

		self.shown_count = min(self.shown_count + PAGE_SIZE, len(self.tracks))
		self.print(bot, chat_id)
	
	
	def toggle(self, bot: TeleBot, chat_id: int, *_):
		self.hidden = not self.hidden
		self.print(bot, chat_id)
	

	@property
	def key_print_next(self):
		return str(id(self)) + '_print_next'

	@property
	def key_toggle(self):
		return str(id(self)) + '_toggle'
