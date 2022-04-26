# matrix-email-bridge

The purpose of this bridge is to send emails back and forth between matrix and an IMAP session. This bridge uses a single room for all emails, and each email thread gets it's own matrix thread. Replying to the email in the thread will send an email to the recipient. Additional emails will be further replies in the thread. Deleting a message in matrix will delete that email. Support for moving and archiving emails does not currently exist, but is planned (eventually).

## How to use
By far, the easiest way to run this bridge is to use the docker image. I use podman but the commands for docker are interchangeable: 
 
1. Create a new room in Matrix using your favorite client
2. Copy the room id (instructions vary by client)
3. Download the bridge ```git clone git@github.com:danastasio/matrix-email-bridge```
4. Change to the downloaded directory ```cd matrix-email-bridge```
5. Build the image ```podman build -t matrix-email-bridge .```
6. Create a volume directory ```mkdir $HOME/matrix-email-bridge```
7. Run the bridge ```podman run -it --rm -v $HOME/matrix-email-bridge:/app/config:Z --name matrix-email-bridge localhost/matrix-email-bridge:latest```
8. The bridge will run and create the config files the first time it is run. Fill out $HOME/matrix-email-bridge/settings.py and $HOME/matrix-email-bridge/secrets.py
9. Run the bridge again. It will stay running this time.

An image on docker hub will be published eventually.

## Installation

## Features
- [X] 100% email -> matrix
- [X] 100% matrix -> email
- [ ] 010% Attachments (WIP)
- [ ] 020% HTML Formatting (WIP)
- [ ] 000% IMAP Idle command
- [ ] 000% Archiving emails
- [ ] 000% Moving to another folder
- [ ] 000% Deleting emails
- [ ] Support for an encrypted room (long term goal. will require rebasing entire code base)
