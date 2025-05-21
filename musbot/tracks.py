import re

from telebot import TeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Dict, Optional, Callable

from .util import word_form_by_num


# Символы, запрещённые в именах файлов
FORBIDDEN_CHARS_REGEX = re.compile(r'[\\|/:*?<>"\x00-\x1F]')
FORBIDDEN_CHARS_REPL = '_'

# Минимальная длина строки для вывода кнопки в Telegram
MIN_LINE_LENGTH = 200

button_events: Dict[str, Callable[[TeleBot, int, int], None]] = {}


class Track:
	def __init__(self, url: str, title: str, author: str,
			  duration: Optional[int] = None,
			  id: Optional[int] = None,
			  is_downloaded: bool = False):
		""" is_downloaded - True, если трек в базе, False, если он не в базе или неизвестно """
		
		self.url = url
		self.title = title
		self.author = author
		self.duration = duration
		self.id = id
		self.is_downloaded = is_downloaded
	
	@property
	def key(self) -> int:
		return str(id(self))


	def format_duration(self) -> str:
		if self.duration is None:
			return '--:--'
		
		hours = self.duration // 3600
		mins = self.duration // 60 % 60
		secs = self.duration % 60

		return f'{hours}:{mins:0>2}:{secs:0>2}' if hours > 0 else f'{mins:0>2}:{secs:0>2}'
	
	
	def get_button_message(self) -> str:
		download_mark = '✅' if self.is_downloaded else ''
		msg = f'{download_mark} {self.format_duration()}   ⸺   {self.author}   ⸺   {self.title}'
		return msg.ljust(MIN_LINE_LENGTH)
	
	def get_filename(self) -> str:
		return re.sub(FORBIDDEN_CHARS_REGEX, FORBIDDEN_CHARS_REPL, f'{self.author} - {self.title}')
	
	
	def __lt__(self, track: object) -> bool:
		if self is track: return False

		if not isinstance(track, Track):
			return NotImplemented
		
		if self.author < track.author: return True
		if self.author > track.author: return False

		if self.title < track.title: return True
		if self.title > track.title: return False

		if self.duration is not None and track.duration is not None:
			if self.duration < track.duration: return True
			if self.duration > track.duration: return False
		
		if self.url < track.url: return True
		if self.url > track.url: return False

		if self.id is not None and track.id is not None:
			if self.id < track.id: return True
			if self.id > track.id: return False

		return False # equals
	
	def __eq__(self, track: object) -> bool:
		if self is track: return True
		if track is None: return False

		if not isinstance(track, Track):
			return NotImplemented
		
		return  self.url      == track.url and\
				self.author   == track.author and\
				self.title    == track.title and\
				self.duration == track.duration and\
				self.id       == track.id
	
	def __ne__(self, track: object) -> bool:
		return not(self == track)


# Размер одной страницы при выводе списка треков
PAGE_SIZE = 10

# Ограничение телеграма на ~55 кнопок (минус 2 кнопки "Свернуть" и "Показать ещё")
MAX_KEYBOARD_SIZE = 53

class TrackPool:
	""" Хранит список треков и номер последнего трека, показанного пользователю """

	def __init__(self, callback: Callable[[Track, TeleBot, int, int], None], tracks: List[Track]):
		self.tracks = tracks
		self.max_pages = (len(tracks) + PAGE_SIZE - 1) // PAGE_SIZE
		self.page = 0
		self.hidden = False
		self.message_id: Optional[int] = None

		for track in tracks:
			button_events[track.key] = lambda *args, _track = track: callback(_track, *args)
		
		if len(tracks) > 0:
			button_events[self.key_print_next] = self.print_next
			button_events[self.key_print_prev] = self.print_prev
			button_events[self.key_delete]     = self.delete
	

	def print(self, bot: TeleBot, chat_id: int):
		""" Выводит группу треков и кнопку "Скрыть" """

		tracks_count = len(self.tracks)
		keyboard = self._create_keyboard() if tracks_count > 0 else None

		if self.message_id is None:
			msg = word_form_by_num(tracks_count,
					f'Найден {tracks_count} трек',
					f'Найдены {tracks_count} трека',
					f'Найдено {tracks_count} треков'
			)

			self.message_id = bot.send_message(chat_id, msg, reply_markup=keyboard).id

		else:
			bot.edit_message_reply_markup(chat_id, self.message_id, reply_markup=keyboard)
	

	def _create_keyboard(self):
		keyboard = InlineKeyboardMarkup()
		keyboard.add(InlineKeyboardButton('Скрыть',  callback_data=self.key_delete))

		for i in range(self.page * PAGE_SIZE, min(len(self.tracks), (self.page + 1) * PAGE_SIZE)):
			track = self.tracks[i]
			keyboard.add(InlineKeyboardButton(track.get_button_message(), callback_data=track.key))
		

		if self.max_pages > 1:
			but_prev =\
				InlineKeyboardButton('← Назад',  callback_data=self.key_print_prev)\
				if self.page > 0 else\
				InlineKeyboardButton(' ',  callback_data='none')
			
			but_page = InlineKeyboardButton(f'{self.page + 1}/{self.max_pages}', callback_data='none')

			but_next =\
				InlineKeyboardButton('Вперёд →', callback_data=self.key_print_next)\
				if self.page < self.max_pages - 1 else\
				InlineKeyboardButton(' ', callback_data='none')
			
			keyboard.add(but_prev, but_page, but_next)
		
		return keyboard
	


	def print_next(self, bot: TeleBot, chat_id: int, *_):
		""" Выводит следующую группу треков """
		self.page = min(self.max_pages, self.page + 1)
		self.print(bot, chat_id)

	def print_prev(self, bot: TeleBot, chat_id: int, *_):
		""" Выводит предыдущую группу треков """
		self.page = max(0, self.page - 1)
		self.print(bot, chat_id)
	
	
	def delete(self, bot: TeleBot, chat_id: int, *_):
		bot.delete_message(chat_id, self.message_id)
	

	@property
	def key_print_next(self):
		return str(id(self)) + '_print_next'

	@property
	def key_print_prev(self):
		return str(id(self)) + '_print_prev'

	@property
	def key_delete(self):
		return str(id(self)) + '_delete'
