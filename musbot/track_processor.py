import os
import requests
import tempfile
import logging

from pydub.utils import mediainfo
from telebot import TeleBot
from typing import Optional

from .file_manager import get_track_path, save_file, create_track_symlink, update_track
from .tracks import Track
from .util import Timer, add_scheme, HEADERS, KEYBOARD_REMOVE


TARGET_BITRATE = int(os.environ.get('TARGET_BITRATE'))
TARGET_FORMAT = os.environ.get('TARGET_FORMAT')
EXT = '.' + TARGET_FORMAT
MAX_SEND_TRIES = int(os.environ.get('MAX_SEND_TRIES'))

logger = logging.getLogger()


def download_track(track: Track, bot: TeleBot, chat_id: int) -> Optional[int]:
	""" Скачивает трек и сохраняет его в файл по пути path """
	
	message_id = bot.send_message(chat_id, 'Скачиваю файл...', reply_markup=KEYBOARD_REMOVE).id

	timer = Timer().start()

	response = requests.get(add_scheme(track.url), headers=HEADERS)

	if not response.ok:
		logger.warning(f'Server returned status {response.status_code} on request {track.url}')
		bot.delete_message(chat_id, message_id)
		bot.send_message(chat_id, 'Ошибка при скачавании файла', reply_markup=KEYBOARD_REMOVE)
		return None

	save_file(track, response)
	
	timer.stop('File downloading')
	
	return message_id


def process_track(track: Track) -> None:
	""" Преобразовывает трек в формат TARGET_FORMAT, сжимает до
		битрейта TARGET_BITRATE и устанавливает метаданные. """
  
	path = get_track_path(track)
	
	timer = Timer().start()
	info = mediainfo(path)
	bitrate = int(info['bit_rate'])
	timer.stop('Mediainfo reading')

	if bitrate > TARGET_BITRATE or info['format_name'] != TARGET_FORMAT:
		with tempfile.NamedTemporaryFile('w+b', suffix=EXT) as tmpfile:
			
			timer.run('ffmpeg', lambda: os.system(
				f'ffmpeg -y -v error -i {path} -f {TARGET_FORMAT}\
						-b:a {min(bitrate, TARGET_BITRATE)} {tmpfile.name}'
			))

	timer.run('Metadata writing', lambda: update_track(track))


def send_file(path: str, bot: TeleBot, chat_id: int) -> None:
	"""
	Отправляет файл в телеграм. Делает MAX_TRIES попыток
	path - путо до симлинка на файл, его название используется телеграмом.
	"""
	
	timer = Timer().start()

	with open(path, 'rb') as file:
		for trying in range(MAX_SEND_TRIES):
			try:
				file.seek(0)
				bot.send_audio(chat_id, file, reply_markup=KEYBOARD_REMOVE)
				break
			except requests.exceptions.ConnectionError as error:
				if trying < MAX_SEND_TRIES - 1:
					logger.warning('Caugth requests.exceptions.ConnectionError, retrying...')
				else:
					raise error

	timer.stop('Audio sending')


def send_track(track: Track, bot: TeleBot, chat_id: int) -> None:
	symlink_path = create_track_symlink(track)
	send_file(symlink_path, bot, chat_id)


def download_process_and_send_track(track: Track, bot: TeleBot, chat_id: int) -> None:
	"""
	Скачивает трек по ссылке и сохраняет его на диск, преобразовывает в формат TARGET_FORMAT,
	сжимает до битрейта TARGET_BITRATE и устанавливает метаданные. Затем отправляет файл в тг.
	"""

	message_id = download_track(track, bot, chat_id)
	process_track(track)
 
	symlink_path = create_track_symlink(track)
	send_file(symlink_path, bot, chat_id)
	
	bot.delete_message(chat_id, message_id)