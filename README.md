# ms-orm
A library for fetching uselful data from DDS medlems-service using ORM

This library first and foremost aims to it easy to access very specific parts of the MedlemsService database as exposed by odoo 8.0 XMLRPC API.
The parts of this database that will be implemented first is the parts I myself use:
* Member (Members being scouts...)
* Events (Events being primarily PLan course)
* Signups (Connections between members and events)

I use this information to help KorpsKontoret distribute "seats" among scouts applying for courses.
The code for this is atm. not publicly available as it relies on some non-free software.

# Requirements
To use this library note:
* The project uses python 3.6 f-strings and async generators. so you *must* use python>=3.6 (yay for bleeding edge!)
* the login module stores credentials. I have no clue how compatible this is with non-linux systems.
  - Q: Why use complicated keyrings for login? 
  - A: I'm vehemently opposed to storing passwords in cleartext.
  
## Using with KWallet
The python package keyring requires the user to do some setup if you do no use gnome-keyring.
Since I had a bit of trouble getting it to work on KDE I wall share the setup steps for kwallet.

* Install python-dbus as a system package (**not thorugh pip!**)
  - on Archlinux : `pacman -S python-dbus`
  - on debian/ubuntu: apt install `python-dbus`
* make the keyring directory: `mkdir -p ~/.local/share/python_keyring/`
* Place a file there called `keyringrc.cfg`
```$cfg
# ~/.local/share/python_keyring/keyringrc.cfg
[backend]
default-keyring = keyring.backends.kwallet.DBusKeyring
```
* install python packacge keyring: `pip3 install keyring --user`
  - Q: Why the `--user` flag?
  - A: You should *never* use pip with sudo, it's a huge security risk...
  
