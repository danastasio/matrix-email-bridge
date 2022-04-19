import requests
import json
import hashlib
import sqlite3
from secrets import Secret
from settings import Settings

class Server:
    base_url = "https://matrix.danastas.io"
    bridge_room = "!hxTlNqTYIXXcPFLgCy:danastas.io"
    
    def set_access_token(self: object) -> None:
        payload = {
            "type": "m.login.password",
            "user": Secret.username,
            "password": Secret.password,
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

    def new_message(self: object, body_text: str) -> str:
        payload = {
            "msgtype": "m.text",
            "body": body_text,
        }
        url = f"{Settings.base_url}/_matrix/client/r0/rooms/{Settings.bridge_room}/send/m.room.message?access_token={self.token}"
        response = requests.post(url, data=json.dumps(payload))
        return json.loads(response.content.decode())['event_id']

    def new_thread_reply(self: object, thread_id: str, last_event: str, body_text: str) -> None:
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
        url = f"{Settings.base_url}/_matrix/client/v3/rooms/{Settings.bridge_room}/send/m.room.message/3?access_token={self.token}"
        response = requests.put(url, data=json.dumps(payload))

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
    def __init__(self: object, subject: str, body: str, imap_id: str):
        self.subject = subject
        self.body = body
        self.imap_id = imap_id
        
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
    bridge.set_access_token()
    prev_batch = bridge.sync()
    response = bridge.get_messages(prev_batch)

    # A new email is received
    email1 = Email("Welcome to the Club!", "Please begin here", "b1e46bc0-6917-4cac-82a1-fce2daac43a7")
    #reply to email1
    email2 = Email("Thanks for following up", "I understand that you have questions. If you need help let us know", "5ef86999-504a-449f-908f-961d5c35fd72")       
    email3 = Email("I have a question", "Hello yes, I have a question about your rates", "f87b9c0a-1a24-4272-a3d0-dbe28128bdd6")

    # TODO Debugging only - remove before prod
    email = email3
    # Find thread from DB based on in_reply_to header from email
    (thread_exists, thread_id, last_event) = db.find_thread(email1.imap_id)

    if db.email_already_logged(email.imap_id):
        # If email already logged to element, do nothing
        pass
    elif thread_exists:
        # If email not logged and thread exists, reply to thread
        bridge.new_thread_reply(thread_id, last_event, email.body)
        db.insert(email.imap_id, thread_id, last_event)
    else:
        # If email not logged and no thread exists, create new top level message
        thread_id = bridge.new_message(email.body)
        last_event = thread_id
        db.insert(email.imap_id, thread_id, last_event)
    
if __name__ == "__main__":
    main()
