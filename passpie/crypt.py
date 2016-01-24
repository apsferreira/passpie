import logging
import os
import re
import shutil

from . import process
from .utils import tempdir
from ._compat import *

from passpie.utils import which


GPG_HOMEDIR = os.path.expanduser('~/.gnupg')
DEVNULL = open(os.devnull, 'w')
KEY_INPUT = u"""Key-Type: RSA
Key-Length: {}
Subkey-Type: RSA
Name-Comment: Auto-generated by Passpie
Passphrase: {}
Name-Real: Passpie
Name-Email: passpie@local
Expire-Date: 0
%commit
"""


def make_key_input(passphrase, key_length):
    passphrase = unicode(passphrase)
    key_length = unicode(key_length)
    key_input = KEY_INPUT.format(key_length, passphrase)
    return key_input


def export_keys(homedir, secret=False):
    command = [
        which('gpg2') or which('gpg'),
        '--no-version',
        '--batch',
        '--homedir', homedir,
        '--export-secret-keys' if secret else '--export',
        '--armor',
        '-o', '-'
    ]
    output, error = process.call(command)
    return output


def create_keys(passphrase, path=None, key_length=4096):
    with tempdir('create_keys') as temp_homedir:
        command = [
            which('gpg2') or which('gpg'),
            '--batch',
            '--no-tty',
            '--homedir', temp_homedir,
            '--gen-key',
        ]
        key_input = make_key_input(passphrase, key_length)
        output, error = process.call(command, input=key_input)

        if path:
            keys_path = os.path.join(temp_homedir, 'keys')
            with open(keys_path, 'w') as keysfile:
                keysfile.write(export_keys(temp_homedir))
                keysfile.write(export_keys(temp_homedir, secret=True))

            new_path = os.path.join(os.path.expanduser(path), '.keys')
            os.rename(keys_path, new_path)
        else:
            return output


def import_keys(homedir, keys_path):
    command = [
        which('gpg2') or which('gpg'),
        '--no-tty',
        '--homedir', homedir,
        '--import', keys_path
    ]
    output, error = process.call(command)
    if error:
        logging.error(error)
    return output


def get_default_recipient(homedir, secret):
    command = [
        which('gpg2') or which('gpg'),
        '--no-tty',
        '--list-{}-keys'.format('secret' if secret else 'public'),
        '--fingerprint',
        '--homedir', homedir,
    ]
    output, error = process.call(command)
    if error:
        logging.error(error)
        return ''
    for line in output.splitlines():
        try:
            mobj = re.search(r'(([0-9A-F]{4}\s*?){10})', line)
            fingerprint = mobj.group().replace(' ', '')
            return fingerprint
        except (AttributeError, IndexError):
            continue
    return ''


class GPG(object):

    def __init__(self, path, recipient=None):
        self.path = os.path.expanduser(path)
        self.keys_path = os.path.join(path, ".keys")
        self.homedir = GPG_HOMEDIR
        self._recipient = recipient

    def __enter__(self):
        return self

    def __exit__(self, exc_ty, exc_val, exc_tb):
        logging.debug('__exit__: {}'.format(self))

    def recipient(self, secret=False):
        if self._recipient:
            # 1. use self.recipient if not None
            recipient = self._recipient
        elif self.keys_path:
            # 2. use default key from .keys if .keys_exist
            with tempdir('homedir') as homedir:
                recipient = get_default_recipient(homedir, secret)
        else:
            # 3. use default key from default homedir
            recipient = get_default_recipient(GPG_HOMEDIR, secret)
        return recipient

    def encrypt(self, data):
        command = [
            which('gpg2') or which('gpg'),
            '--batch',
            '--no-tty',
            '--always-trust',
            '--armor',
            '--recipient', self.recipient(),
            '--homedir', self.homedir,
            '--encrypt'
        ]
        output, error = process.call(command, input=data)
        if error:
            logging.error(error)
        return output

    def decrypt(self, data, passphrase):
        command = [
            which('gpg2') or which('gpg'),
            '--batch',
            '--no-tty',
            '--always-trust',
            '--recipient', self.recipient(secret=True),
            '--homedir', self.homedir,
            '--passphrase', passphrase,
            '--emit-version',
            '-o', '-',
            '-d', '-',
        ]
        output, error = process.call(command, input=data)
        if error:
            logging.error(error)
        return output

    def __str__(self):
        return "GPG(path={0.path}, homedir={0.homedir})".format(self)
