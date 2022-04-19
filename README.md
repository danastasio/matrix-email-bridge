# matrix-email-bridge

The purpose of this bridge is to send emails back and forth between matrix and an IMAP session. This bridge uses a single room for all emails, and each email thread gets it's own matrix thread. Replying to the email in the thread will send an email to the recipient. Additional emails will be further replies in the thread. Deleting a message in matrix will delete that email. Support for moving and archiving emails does not currently exist, but is planned (eventually).

## How it works

## Installation

## Features
- [ ] email -> matrix
- [ ] matrix -> email
- [ ] Archiving emails
- [ ] Moving to another folder
- [ ] Deleting emails
