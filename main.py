import time
import json
import email
import hashlib
import sqlite3
import requests
from secrets import Secrets
from settings import Settings
from imapclient import IMAPClient

class Server:
	def set_access_token(self: object) -> None:
		payload = {
			"type": "m.login.password",
			"user": Secrets.username,
			"password": Secrets.password,
		}
		url = f"{Settings.base_url}/_matrix/client/r0/login"
		response = requests.post(url, data=json.dumps(payload))
		response = json.loads(response.content.decode())
		self.token = response['access_token']

	def sync(self: object) -> str:
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
					"!hxTlNqTYIXXcPFLgCy:danastas.io",
				],
			},
		}
		url = f"{Settings.base_url}/_matrix/client/v3/sync?access_token={self.token}&filter={json.dumps(filter)}"
		response = json.loads(requests.get(url).content.decode())
		#print(json.dumps(response, indent=4, separators=(', ', ': ')))
		return response['rooms']['join'][Settings.bridge_room]['timeline']['prev_batch']

	def get_messages(self: object, prev_batch: str) -> dict:
		filter = {
			"types": [
				"m.room.message",
			]
		}
		url = f"{Settings.base_url}/_matrix/client/v3/rooms/{Settings.bridge_room}/messages?access_token={self.token}&dir=f&from={prev_batch}&filter={json.dumps(filter)}"
		return json.loads(requests.get(url).content.decode())

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
		#url = f"{Settings.base_url}/_matrix/client/v3/rooms/{Settings.bridge_room}/send/m.room.message/3?access_token={self.token}"
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
	def insert(self: object, imap_id, thread_id: str, latest_event: str):
		conn = sqlite3.connect('database.db')
		cursor = conn.cursor()
		cursor.execute(f'''INSERT INTO email_matrix (imap_id, thread_id, latest_event)
		  VALUES(?, ?, ?);''', (imap_id, thread_id, latest_event))
		conn.commit()

	def find_thread(self: object, imap_id: str) -> tuple:
		thread_id = None
		latest_event = None
		conn = sqlite3.connect('database.db')
		cursor = conn.cursor()
		cursor.execute(f"SELECT thread_id, latest_event FROM email_matrix WHERE imap_id=?", (imap_id,))
		results = cursor.fetchall()
		for row in results:
			thread_id = row[0]
			latest_event = row[1]
		return (len(results) != 0, thread_id, latest_event)

	def email_already_logged(self: object, imap_id: str):
		conn = sqlite3.connect('database.db')
		cursor = conn.cursor()
		cursor.execute(f"SELECT thread_id, latest_event FROM email_matrix WHERE imap_id=?", (imap_id,))
		results = cursor.fetchall()
		return len(results) != 0

class Email:
	def __init__(self: object, imap_id: str, subject: str, in_reply_to: str, sender: str):
		self.subject = subject
		self.imap_id = imap_id
		self.in_reply_to = in_reply_to
		self.sender = sender

	@staticmethod
	def refresh_inbox() -> list:
		email_list: list = []
		with IMAPClient(host=Settings.email_server) as client:
			client.login(Secrets.email_username, Secrets.email_password)
			client.select_folder('INBOX')
			messages = client.search(['NOT', 'DELETED'])
			#response = client.fetch(messages, ['ENVELOPE', 'RFC822', 'BODY'])
			for uid, message_data in client.fetch(messages, ["RFC822"]).items():
				body = None
				email_message = email.message_from_bytes(message_data[b"RFC822"])
				current_email = Email(email_message.get("Message-ID"), email_message.get("Subject"), email_message.get("In-Reply-To"), email_message.get("From"))
				if email_message.is_multipart():
					for part in email_message.walk():
						ctype = part.get_content_type()
						cdispo = str(part.get('Content-Disposition'))
					
						# skip any text/plain (txt) attachments
						if ctype == 'text/plain' and 'attachment' not in cdispo:
							body = part.get_payload(decode=True)  # decode
							break
				# not multipart - i.e. plain text, no attachments, keeping fingers crossed
				else:
					body = email_message.get_payload(decode=True)
				try:
					current_email.body = body.decode()
				except:
					pass
				email_list.append(current_email)
		return email_list
	
class Message:
	'''
	A Class to hold information about the matrix message
	'''
	def __init__(self: object, thread_id: str, event_id: str):
		self.thread_id = thread_id
		self.event_id = event_id

def main():
	bridge = Server()
	db = Database()
	
	while True:
		#time.sleep(Settings.sleep_time)
		#time.sleep(10)
		bridge.set_access_token()
		prev_batch = bridge.sync()
		response = bridge.get_messages(prev_batch)

		emails = Email.refresh_inbox()
		
		for current_email in emails: 
			# Find thread from DB based on in_reply_to header from email
			(thread_exists, thread_id, last_event) = db.find_thread(current_email.in_reply_to) 

			if db.email_already_logged(current_email.imap_id):
				# If email already logged to element, do nothing
				pass
			elif thread_exists:
				# If email not logged and thread exists, reply to thread
				err_code = bridge.new_thread_reply(thread_id, last_event, current_email.body)
				if err_code == "event too large":
					bridge.new_thread_reply(thread_id, last_event, "Event too large. View in a different application.")
				db.insert(current_email.imap_id, thread_id, last_event)
			else:
				# If email not logged and no thread exists, create new top level message with subject, and first reply with body
				thread_id = bridge.new_message(current_email.subject, current_email.sender)
				last_event = bridge.new_thread_reply(thread_id, last_event, str(current_email.body))
				if last_event == "event too large":
					bridge.new_thread_reply(thread_id, last_event, "Event too large. View in a different application.")
				db.insert(current_email.imap_id, thread_id, last_event)

if __name__ == "__main__":
	main()
