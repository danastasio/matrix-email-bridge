import os
import time
import json
import email
import smtplib
import sqlite3
import requests
from email import utils
from config.secrets import Secrets
from config.settings import Settings
from imapclient import IMAPClient
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

class Setup:
	def is_first_run() -> bool:
		return not os.path.isfile('/app/config/settings.py')

	def settings() -> None:
		if not os.path.isfile('/app/config/settings.py'):
			with open('/app/config/settings.py', 'w') as file:
				file.write('''class Settings:
	base_url:	str = "https://matrix.org"
	bridge_room:	str = "!hxTlNqTYIXXcPFLgCy:matrix.org"
	sleep_time:	int = 10
	imap_server:	str = "imap.gmail.com"
	imap_port:	str = "993"
	smtp_server:	str = "smtp.gmail.com"
	smtp_port:	str = "587"
	use_starttls:	bool = True
	email_address:	str = ""
	email_domain:	str = "gmail.com"''')

			with open('/app/config/__init__.py', 'w') as file:
				pass

	def secrets() -> None:
		if not os.path.isfile('/app/config/secrets.py'):
			with open('/app/config/secrets.py', 'w') as file:
				file.write('''class Secrets:
	matrix_password: str = ""
	matrix_username: str = "" # localpart only, do not include @
	email_username:  str = ""
	email_password:  str = ""''')

class Server:
	def set_access_token(self: object) -> None:
		payload = {
			"type": "m.login.password",
			"user": Secrets.matrix_username,
			"password": Secrets.matrix_password,
		}
		url = f"{Settings.base_url}/_matrix/client/r0/login"
		response = requests.post(url, data=json.dumps(payload))
		response = json.loads(response.content.decode())
		self.token = response['access_token']

	def sync(self: object) -> tuple:
		filter = {
			"account_data": {
				"limit": 0,
				"not_types": [
					"m.*",
					"im.*",
					"io.element.recent_emoji",
				],
			},
			"presence": {
				"not_types": [
					"m.presence",
				]
			},
			"room": {
				"rooms": [
					Settings.bridge_room,
				],
			},
		}
		url = f"{Settings.base_url}/_matrix/client/v3/sync?access_token={self.token}&filter={json.dumps(filter)}"
		response = json.loads(requests.get(url).content.decode())
		#print(json.dumps(response, indent=4, separators=(', ', ': ')))
		return (response['rooms']['join'][Settings.bridge_room]['timeline']['prev_batch'], response['rooms']['join'][Settings.bridge_room]['timeline']['events'], response['next_batch'])

	def get_messages(self: object, prev_batch: str) -> dict:
		filter = {
			"types": [
				"m.room.message",
			]
		}
		url = f"{Settings.base_url}/_matrix/client/v3/rooms/{Settings.bridge_room}/messages?access_token={self.token}&dir=f&from={prev_batch}&filter={json.dumps(filter)}"
		response = json.loads(requests.get(url).content.decode())
		return response

	def new_message(self: object, subject: str, sender: str) -> str:
		payload = {
			"msgtype": "m.text",
			"body": f"Subject: {subject}\n\nFrom: {sender}",
		}
		url = f"{Settings.base_url}/_matrix/client/r0/rooms/{Settings.bridge_room}/send/m.room.message?access_token={self.token}"
		response = requests.post(url, data=json.dumps(payload))
		return json.loads(response.content.decode())['event_id']

	def new_thread_reply(self: object, thread_id: str, last_event: str, body_text: str) -> str:
		body_text = body_text
		payload = {
			"org.matrix.msc1767.text": body_text,
			"body": body_text,
			"msgtype": "m.text",
			"m.relates_to": {
				"rel_type": "m.thread",
				"event_id": thread_id,
				"is_falling_back": True,
				"m.in_reply_to": {
					"event_id": last_event,
				},
			},
		}
		url = f"{Settings.base_url}/_matrix/client/r0/rooms/{Settings.bridge_room}/send/m.room.message?access_token={self.token}"
		response = requests.post(url, data=json.dumps(payload))
		if json.loads(response.content.decode()).get('errcode') == "M_TOO_LARGE":
			return "event too large"
		else:
			return json.loads(response.content.decode())['event_id']

	def thread_endpoint(self: object):
		'''
		Not published yet
		'''
		url = f"{Settings.base_url}/_matrix/client/v3/rooms/{Settings.bridge_room}/thread"
		room = [Settings.bridge_room]
		response = requests.post(url, data=json.dumps(room))
		print(response.content.decode())

class Database:
	def __init__(self: object):
		self.conn = sqlite3.connect('database.db')
		conn = self.conn.cursor()
		table = '''CREATE TABLE if not exists email_matrix (
			id INTEGER PRIMARY KEY,
			imap_id TEXT NOT NULL UNIQUE,
			thread_id TEXT NOT NULL,
			event_id TEXT NOT NULL,
			sender TEXT,
			subject TEXT
		)'''
		conn.execute(table)

	def insert(self: object, imap_id, thread_id: str, event_id: str, reply_to: str):
		cursor = self.conn.cursor()
		cursor.execute(f'''INSERT INTO email_matrix (imap_id, thread_id, event_id, sender)
		  VALUES(?, ?, ?, ?);''', (imap_id, thread_id, event_id, json.dumps(reply_to)))
		self.conn.commit()

	def find_thread(self: object, imap_id: str) -> tuple:
		thread_id = None
		event_id = None
		cursor = self.conn.cursor()
		cursor.execute(f"SELECT thread_id, event_id FROM email_matrix WHERE imap_id=?", (imap_id,))
		results = cursor.fetchall()
		for row in results:
			thread_id = row[0]
			event_id = row[1]
		return (len(results) != 0, thread_id, event_id)

	def find_original_message(self: object, thread_id: str) -> str:
		cursor = self.conn.cursor()
		cursor.execute(f"SELECT sender, imap_id, subject FROM email_matrix WHERE event_id=? ORDER BY id LIMIT 1", (thread_id,))
		results = cursor.fetchall()
		for row in results:
			sender = row[0]
			in_reply_to = row[1]
			subject = row[2]
		return (sender, in_reply_to, subject)

	def email_already_logged(self: object, imap_id: str) -> bool:
		cursor = self.conn.cursor()
		sender = None
		query = f"SELECT thread_id, event_id FROM email_matrix WHERE imap_id={(imap_id,)}"
		cursor.execute(f"SELECT thread_id, event_id FROM email_matrix WHERE imap_id=?", (imap_id,))
		results = cursor.fetchall()
		return len(results) != 0

	def message_already_logged(self: object, event_id: str) -> bool:
		sender = None
		imap_id = None
		cursor = self.conn.cursor()
		cursor.execute(f"SELECT sender, imap_id FROM email_matrix WHERE event_id=?", (event_id,))
		results = cursor.fetchall()
		return len(results) != 0

class Email:
	def __init__(self: object, imap_id: str, subject: str, in_reply_to: str, sender: str, reply_to: str):
		self.subject: str =		subject
		self.imap_id: str =		imap_id
		self.in_reply_to: str =	in_reply_to
		self.sender: str =		sender
		self.reply_to: list =	reply_to
		self.bridged_reply: bool = False

	@staticmethod
	def refresh_inbox() -> list:
		email_list: list = []
		with IMAPClient(host=Settings.imap_server) as client:
			client.login(Secrets.email_username, Secrets.email_password)
			client.select_folder('INBOX')
			messages = client.search(['NOT', 'DELETED'])
			for uid, message_data in client.fetch(messages, ["RFC822", "ENVELOPE"]).items():
				body = None
				email_message = email.message_from_bytes(message_data[b"RFC822"])
				reply_emails = []
				for sender in message_data[b'ENVELOPE'].reply_to:
					reply_emails.append(f"{sender.mailbox.decode()}@{sender.host.decode()}")
				current_email = Email(email_message.get("Message-ID"), message_data[b'ENVELOPE'].subject.decode(), email_message.get("In-Reply-To", '').strip(), email_message.get("From"), reply_emails)
				if "Matrix-Bridged-Email" in email_message:
					current_email.bridged_reply = True
				if email_message.is_multipart():
					for part in email_message.walk():
						ctype = part.get_content_type()
						cdispo = str(part.get('Content-Disposition'))
						# skip any text/plain (txt) attachments
						if ctype == 'text/text' and 'attachment' not in cdispo:
							body = part.get_payload(decode=True)  # decode
							break
				# not multipart - i.e. plain text, no attachments, keeping fingers crossed
				else:
					body = email_message.get_payload(decode=True)
				try:
					current_email.body = body.decode()
				except:
					current_email.body = "General error"
				email_list.append(current_email)
		return email_list

	@staticmethod
	def send(subject: str, to_addrs: str, body: str, imap_id) -> str:
		message = MIMEMultipart('alternative')
		message['Subject'] = subject
		message['From'] = Settings.email_address
		message['To'] = f"{ ','.join(to_addrs) }"
		message['In-Reply-To'] = imap_id
		message['References'] = imap_id
		message['Matrix-Bridged-Email'] = "True"
		message['Message-ID'] = utils.make_msgid(domain="davidanastasio.com")
		text = "Please display this email as HTML"
		part1 = MIMEText(text, 'plain')
		part2 = MIMEText(body, 'html')
		message.attach(part1)
		message.attach(part2)
		server = smtplib.SMTP(Settings.smtp_server, Settings.smtp_port)
		server.starttls()
		server.login(Secrets.email_username, Secrets.email_password)
		server.sendmail(Settings.email_address, to_addrs, message.as_string())
		return message['Message-ID']

class Message:
	'''
	A Class to hold information about the matrix message
	'''
	def __init__(self: object, type: str, body: str, event_id: str, thread_id: str):
		self.type = type
		self.body = body
		self.event_id = event_id
		self.thread_id = thread_id
		self.logged = False
		self.subject = ''

	@property
	def reply_to(self: object):
		return self._reply_to

	@reply_to.setter
	def reply_to(self: object, addresses: str) -> json:
		self._reply_to = json.loads(addresses)

def main():
	if Setup.is_first_run():
		print("Running setup tasks...")
		Setup.settings()
		Setup.secrets()
		print("Setup complete. Please configure settings.py and secrets.py")
		quit()
	print("Connecting bridge")
	bridge = Server()
	print("Connecting database")
	db = Database()
	print("Setting access token")
	bridge.set_access_token()
	print("Syncing...")
	(prev_batch, sync_data, next_batch) = bridge.sync()
	print("Sync done")

	while True:
		print("Starting loop again")
		print(f"Sleeing for {Settings.sleep_time}")
		time.sleep(Settings.sleep_time)
		emails = Email.refresh_inbox()

		for current_email in emails: 
			# Find thread from DB based on in_reply_to header from email
			(thread_exists, thread_id, last_event) = db.find_thread(current_email.in_reply_to) 
			if db.email_already_logged(current_email.imap_id):
				# If email already logged to element, do nothing
				continue
			elif thread_exists:
				# If email not logged and thread exists, reply to thread
				if current_email.bridged_reply:
					# Skip replies that we send from Matrix
					continue
				print("New email reply detected")
				err_code = bridge.new_thread_reply(thread_id, last_event, current_email.body)
				if err_code == "event too large":
					bridge.new_thread_reply(thread_id, last_event, "Event too large. View in a different application.")
				db.insert(current_email.imap_id, thread_id, last_event, current_email.reply_to)
			else:
			# If email not logged and no thread exists, create new top level message with subject, and first reply with body
				if current_email.bridged_reply:
					# Skip replies that we send from Matrix
					continue
				print("New email detected")
				thread_id = bridge.new_message(current_email.subject, current_email.sender)
				last_event = bridge.new_thread_reply(thread_id, last_event, str(current_email.body))
				if last_event == "event too large":
					bridge.new_thread_reply(thread_id, last_event, "Event too large. View in a different application.")
				db.insert(current_email.imap_id, thread_id, thread_id, current_email.reply_to)

		# Check for new messages in element that need to be sent to email
		response = bridge.get_messages(next_batch)
		for event in response['chunk']:
			try:
				message = Message(event['type'], event['content']['body'], event['event_id'], event['content']['m.relates_to']['event_id'])
			except KeyError:
				message = Message(event['type'], event['content']['body'], event['event_id'], event['unsigned']['m.relations']['m.thread']['latest_event']['content']['m.relates_to']['event_id'])

			# If event_id from response is not in DB, assume new message and send the body along
			message.logged = db.message_already_logged(message.event_id)
			(message.reply_to, message.imap_id, message.subject) = db.find_original_message(message.thread_id)

			if message.logged:
				pass
			else:
				# TODO Store subject in DB and fix
				print("Matrix reply detected - sending email")
				sent_message_id = Email.send(message.subject, message.reply_to, message.body, message.imap_id)
				db.insert(sent_message_id, message.thread_id, message.event_id, message.reply_to)
		next_batch = response['end']

if __name__ == "__main__":
	main()
