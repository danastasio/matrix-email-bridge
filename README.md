# matrix-email-bridge

The purpose of this bridge is to send emails back and forth between matrix and an IMAP session. This bridge uses a single room for all emails, and each email thread gets it's own matrix thread. Replying to the email in the thread will send an email to the recipient. Additional emails will be further replies in the thread. Deleting a message in matrix will delete that email. Support for moving and archiving emails does not currently exist, but is planned (eventually).

## How it works

## Installation

## Features
- [X] 100% email -> matrix
- [ ] 000% matrix -> email
- [ ] Attachments
- [ ] 000% Archiving emails
- [ ] 000% Moving to another folder
- [ ] 000% Deleting emails
