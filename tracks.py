import urllib.parse
import requests
import re

from bs4 import BeautifulSoup
from typing import List, Dict, Optional

HOST = 'https://web.ligaudio.ru'

HEADERS = {
	'Accept': 'text/html',
	'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 12_3_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.4 Safari/605.1.15',
}

FORBIDDEN_CHARS = re.compile(r'[\\/:*?<>"\x00-\x1F|]')


class Track:
	__cache: Dict[int, str] = {}

	def __init__(self, url: str, title: str, author: str, duration: str):
		self.url = url
		self.title = title
		self.author = author
		self.duration = duration
		Track.__cache[id(self)] = self
	
	@property
	def id(self) -> int:
		return id(self)


	@staticmethod
	def get_cached(id: int) -> Optional['Track']:
		return Track.__cache.get(id)
	
	def get_text(self) -> str:
		return f'{self.author}   ⸺   {self.title}   ⸺   {self.duration}'
	
	def get_filename(self) -> str:
		return re.sub(FORBIDDEN_CHARS, '_', f'{self.author} - {self.title}')


def __add_tracks(tracks: List[Track], req_author: Optional[str], req_title: Optional[str], url: str) -> BeautifulSoup:
	""" Добавляет совпадающие треки в переданный список. Возвращает страницу. """

	response = requests.get(url, HEADERS)
	soup = BeautifulSoup(response.text, 'lxml')

	for tag in soup.find_all('div', {'itemprop': 'track'}):
		href = 'https:' + tag.find('a', {'itemprop': 'url'})['href']

		title = tag.find('span', {'class': 'title', 'itemprop': 'name'}).get_text()
		if req_title is not None and title.lower().find(req_title.lower()) == -1:
			continue

		author = tag.find('span', {'class': 'autor', 'itemprop': 'byArtist'}).get_text()
		if req_author is not None and author.lower().find(req_author.lower()) == -1:
			continue

		time = tag.find('span', {'class': 'd'}).get_text()

		tracks.append(Track(href, title, author, time))
	
	return soup


def load_tracks(request: str, req_author: Optional[str], req_title: Optional[str]) -> List[Track]:
	""" Возвращает список треков по запросу """

	tracks = []
	url = urllib.parse.urljoin(HOST, 'mp3/' + urllib.parse.quote(request, safe=''))

	soup = __add_tracks(tracks, req_author, req_title, url)

	pagination = soup.find('div', {'class': 'pagination'})

	if pagination is not None:
		for link in pagination.find_all('a'):
			if 'this' not in link.get_attribute_list('class'):
				__add_tracks(tracks, req_author, req_title, urllib.parse.urljoin(HOST, link['href']))


	print(f'Found {len(tracks)} tracks on page {url}')
	return tracks