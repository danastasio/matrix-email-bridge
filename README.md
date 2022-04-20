# matrix-email-bridge

The purpose of this bridge is to send emails back and forth between matrix and an IMAP session. This bridge uses a single room for all emails, and each email thread gets it's own matrix thread. Replying to the email in the thread will send an email to the recipient. Additional emails will be further replies in the thread. Deleting a message in matrix will delete that email. Support for moving and archiving emails does not currently exist, but is planned (eventually).

## How to use
1. Create a new room in Matrix using your favorite client
2. Copy the room id (instructions vary by client)
3. Download the bridge ```git clone git@github.com:danastasio/matrix-email-bridge```
4. Change to the downloaded directory ```cd matrix-email-bridge```
5. Copy example_settings.py to settings.py
6. Copy example_secrets.py to secrets.py
7. Fill out both secrets.py and settings.py with your own values
8. Create a python venv ```python -m venv .```
9. Install dependencies ```pip install -r requirements.txt```
10. Activate the venv ```source bin/activate```
11. Run the script ```python main.py```

A docker image will be coming eventually, but it is not built yet.

## Installation

## Features
- [X] 100% email -> matrix
- [X] 100% matrix -> email
- [ ] Attachments
- [ ] HTML Formatting
- [ ] IMAP Idle command
- [ ] 000% Archiving emails
- [ ] 000% Moving to another folder
- [ ] 000% Deleting emails
- [ ] Support for an encrypted room (long term goal)
