import os
import psycopg2

from telebot.types import User
from typing import List, Optional

from .tracks import Track

def init() -> None:
	global connection, cursor
	
	connection = psycopg2.connect(
		dbname   = os.environ.get('DB_NAME'),
		host     = os.environ.get('DB_HOST'),
		port     = os.environ.get('DB_PORT'),
		user     = os.environ.get('DB_USER'),
		password = os.environ.get('DB_PASSWORD')
	)

	cursor = connection.cursor()

	cursor.execute("""CREATE TABLE IF NOT EXISTS users (
					id BIGINT PRIMARY KEY,
					name VARCHAR(65536) NOT NULL
			   )""")

	cursor.execute("""CREATE TABLE IF NOT EXISTS tracks (
						id SERIAL PRIMARY KEY,
						user_id BIGINT NOT NULL REFERENCES users(id),
						url VARCHAR(2048) NOT NULL,
						title VARCHAR(2048) NOT NULL,
						author VARCHAR(2048) NOT NULL,
						duration SMALLINT,
						UNIQUE(user_id, url)
					)""")
	
	connection.commit()


def cleanup() -> None:
	cursor.close()
	connection.close()


def add_or_update_user(user: User) -> None:
	cursor.execute("""INSERT INTO users (id, name) VALUES (%s, %s)
					  ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name""",
				   (user.id, user.username))
	
	connection.commit()


def add_or_update_track(user_id: int, track: Track) -> None:
	cursor.execute("""INSERT INTO tracks (user_id, url, title, author, duration)
					  VALUES (%s, %s, %s, %s, %s)
					  ON CONFLICT (user_id, url)
					  DO UPDATE SET title=EXCLUDED.title, author=EXCLUDED.author, duration=EXCLUDED.duration""",
				   (user_id, track.url, track.title, track.author, track.duration))
	
	connection.commit()


def _escape_like_pattern(string: str) -> str:
	return '%' + string.replace('=', '==').replace('%', '=%').replace('_', '=_') + '%'


def get_track_list(user_id: int, title: Optional[str], author: Optional[str]) -> List[Track]:
	query = "SELECT id, url, title, author, duration FROM tracks WHERE user_id = %s"
	args = [user_id]
	
	if title is not None:
		query += " AND title ILIKE %s ESCAPE '='"
		args.append(_escape_like_pattern(title))
	
	if author is not None:
		query += " AND author ILIKE %s ESCAPE '='"
		args.append(_escape_like_pattern(author))
	
	query += " ORDER BY author, title DESC"
	
	cursor.execute(query, args)
	connection.commit()
	
	return list(map(
		lambda row: Track(id=row[0], url=row[1], title=row[2], author=row[3], duration=row[4], is_downloaded=True),
		cursor
	))


def update_track(track: Track) -> None:
	cursor.execute("UPDATE tracks SET url=%s, title=%s, author=%s, duration=%s WHERE id=%s",
				   (track.url, track.title, track.author, track.duration, track.id))

	connection.commit()


def delete_track(track: Track) -> None:
	cursor.execute("DELETE FROM tracks WHERE id=%s", (track.id,))
	connection.commit()


def set_is_downloaded(user_id: int, tracks: List[Track]) -> None:
	""" Для каждого трека устанавливает is_downloaded в True, если трек есть в базе """

	if len(tracks) == 0: return

	urls = tuple(track.url for track in tracks)

	cursor.execute("SELECT url FROM tracks WHERE user_id=%s AND url IN %s", (user_id, urls))
	connection.commit()
	
	found_urls = set(row[0] for row in cursor)
	for track in tracks:
		track.is_downloaded = track.url in found_urls