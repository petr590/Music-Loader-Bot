from abc import abstractmethod
from typing import Dict, Type
from telebot import TeleBot, types

from . import database
from .tracks import Track
from .track_processor import process_track

class Action:
	"""
	Действие - абстракция над сообщениями telebot. Каждое действие может вернуть себя
	или другое действие, так организуется "переход" между ними.
	"""

	def __init__(self, track: Track) -> None:
		self.track = track
	
	def filter(self, message: types.Message) -> bool:
		"""
		Возвращает True, если сообщение применимо к действию.
		По умолчанию всегда возвращает True.
		"""
		return True
	
	@abstractmethod
	def handle_message(self, message: types.Message, bot: TeleBot) -> 'Action':
		"""
		Выполняет очередное действие. Возвращает следующее действие
		(возможно, self), если действие не окончено, иначе NO_ACTION.
		"""


class NoAction(Action):
	"""
	Представляет отсутствие действия в данный момент.
	Никогда не обрабатывается, так как метод filter всегда возвращает False.
	Может быть заменено на друге действие только вручную.
	"""

	def __init__(self) -> None:
		super().__init__(None)
	
	@staticmethod
	def getter(track: Track) -> 'NoAction':
		return NO_ACTION
	
	def filter(self, message: types.Message) -> bool:
		return False
	
	def handle_message(self, message: types.Message, bot: TeleBot) -> Action:
		return self


# Единственный экземпляр класса
NO_ACTION = NoAction()

KEYBOARD_REMOVE = types.ReplyKeyboardRemove()

class EditAction(Action):
	def __init__(self, track: Track, edit_message: str) -> None:
		super().__init__(track)
		self._edit_message = edit_message
		self._second_stage = False
	
	def handle_message(self, message: types.Message, bot: TeleBot) -> Action:
		if not self._second_stage:
			bot.send_message(message.chat.id, self._edit_message, reply_markup=KEYBOARD_REMOVE)
			self._second_stage = True
			return self
		else:
			self.track.author = message.text
			database.update_track(self.track)
			bot.send_message(message.chat.id, 'Трек изменён')
			return NO_ACTION
	
	@abstractmethod
	def _edit(self, message: str) -> None:
		""" Редактирует self.track """


class EditAuthorAction(EditAction):
	def __init__(self, track: Track) -> None:
		super().__init__(track, 'Введите нового автора трека')
	
	def _edit(self, message: str):
		self.track.author = message


class EditTitleAction(EditAction):
	def __init__(self, track: Track) -> None:
		super().__init__(track, 'Введите новое название трека')
	
	def _edit(self, message: str):
		self.track.title = message


class DownloadTrackAction(Action):
	def __init__(self, track: Track) -> None:
		super().__init__(track)

	def handle_message(self, message: types.Message, bot: TeleBot) -> Action:
		process_track(self.track, bot, message.chat.id)
		return NO_ACTION


class DeleteTrackAction(Action):
	__keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True).add(
		types.KeyboardButton('Да'),
		types.KeyboardButton('Нет'),
	)

	def __init__(self, track: Track) -> None:
		super().__init__(track)
		self._second_stage = False

	def handle_message(self, message: types.Message, bot: TeleBot) -> Action:
		if not self._second_stage:
			bot.send_message(message.chat.id, 'Вы уверены?', reply_markup=DeleteTrackAction.__keyboard)
			self._second_stage = True
			return self
		
		if message.text.lower() == 'да':
			database.delete_track(self.track)
			bot.send_message(message.chat.id, 'Трек удалён', reply_markup=KEYBOARD_REMOVE)
		else:
			bot.send_message(message.chat.id, 'Отменено', reply_markup=KEYBOARD_REMOVE)

		return NO_ACTION



ACTION_BY_BUTTON_MESSAGE: Dict[str, Type[Action]] = {
	'Изменить автора':   EditAuthorAction,
	'Изменить название': EditTitleAction,
	'Скачать':           DownloadTrackAction,
	'Удалить':           DeleteTrackAction,
}


class ChooseAction(Action):
	def __init__(self, track: Track) -> None:
		super().__init__(track)
	
	def filter(self, message: types.Message) -> bool:
		return message.text in ACTION_BY_BUTTON_MESSAGE
	
	def handle_message(self, message: types.Message, bot: TeleBot) -> Action:
		return ACTION_BY_BUTTON_MESSAGE.get(message.text, NoAction.getter)(self.track)\
			.handle_message(message, bot)
