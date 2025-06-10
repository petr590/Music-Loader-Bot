import os.path
import requests
import logging

from typing import Optional
from mutagen.easyid3 import EasyID3
from .tracks import Track

TRACKS_DIR = os.environ.get('TRACKS_DIR')
EXT = '.' + os.environ.get('TARGET_FORMAT')

logger = logging.getLogger()


def get_track_path(track: Track) -> str: 
	if track.id is None:
		raise ValueError('track.id is None')

	return os.path.join(TRACKS_DIR, 'DB', str(track.id) + EXT)

def _get_symlink_path(track: Track) -> str:
	return os.path.join(os.path.join(TRACKS_DIR, track.get_dirname(), track.get_filename() + EXT))


def _remove_if_exists(path: str) -> None:
	if os.path.exists(path):
		os.remove(path)



def save_file(track: Track, response: requests.Response) -> None:
	with open(get_track_path(track), '+wb') as file:
		file.write(response.content)


def create_track_symlink(track: Track) -> str:
	""" Создаёт симлинк с именем трека """
	symlink_path = _get_symlink_path(track)

	if not os.path.exists(symlink_path):
		os.makedirs(os.path.dirname(symlink_path), exist_ok=True)
		os.symlink(get_track_path(track), symlink_path)
	
	return symlink_path


def update_track(track: Track, old_track: Optional[Track] = None) -> None:
	"""
	Обновляет метаданные в файле трека и создаёт симлинк, если его нет.
	old_track - если не None, то удаляет симлинк для старого трека.
	"""
    
	id3 = EasyID3(get_track_path(track))
	id3.clear()
	id3['title'] = track.title
	id3['artist'] = track.author
	id3.save()

	if old_track is not None:
		_remove_if_exists(_get_symlink_path(old_track))
	
	create_track_symlink(track)


def delete_track(track: Track) -> None:
	""" Удаляет файл трека и симлинк на него """
    
	_remove_if_exists(_get_symlink_path(track))
	_remove_if_exists(get_track_path(track))
