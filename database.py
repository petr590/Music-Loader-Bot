import os
import re
import psycopg2

from telebot.types import User

from tracks import Track

def init():
	global connection, cursor
	
	connection = psycopg2.connect(
		dbname   = os.environ.get('DB_NAME'),
		host     = os.environ.get('DB_HOST'),
		port     = os.environ.get('DB_PORT'),
		user     = os.environ.get('DB_USER'),
		password = os.environ.get('DB_PASSWORD')
	)

	cursor = connection.cursor()

	cursor.execute('''CREATE TABLE IF NOT EXISTS users (
					id BIGINT PRIMARY KEY,
					name VARCHAR(65536) NOT NULL
			   )''')

	cursor.execute('''CREATE TABLE IF NOT EXISTS tracks (
						id SERIAL PRIMARY KEY,
						user_id BIGINT NOT NULL REFERENCES users(id),
						url VARCHAR(2048) NOT NULL,
						title VARCHAR(2048) NOT NULL,
						author VARCHAR(2048) NOT NULL,
						UNIQUE(user_id, url)
					)''')

	connection.commit()


def cleanup():
	cursor.close()
	connection.close()


def add_or_update_user(user: User):
	cursor.execute('''INSERT INTO users (id, name) VALUES (%s, %s)
					  ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name''',
				   (user.id, user.username))
	
	connection.commit()


URL_REGEX = re.compile(r'^https?://', re.I)

def add_track_info(user_id: int, track: Track):
	url = re.sub(URL_REGEX, '', track.url)

	cursor.execute('''INSERT INTO tracks (user_id, url, title, author)
					  VALUES (%s, %s, %s, %s)
					  ON CONFLICT (user_id, url)
					  DO UPDATE SET title=EXCLUDED.title, author=EXCLUDED.author''',
				   (user_id, url, track.title, track.author))
	
	connection.commit()