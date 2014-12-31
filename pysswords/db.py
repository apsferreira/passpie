from collections import namedtuple
import fnmatch
import os
import gnupg
import yaml

from .utils import which

Credential = namedtuple("Credential", "name login password comment")


class Database(object):


    @classmethod
    def content(cls, credential):
        return yaml.dump(credential)

    @classmethod
    def create(cls, path):
        os.makedirs(path)
        return Database(path)

    def __init__(self, path):
        self.path = path

    @property
    def gpg(self):
        return gnupg.GPG(binary=which("gpg"),
                         homedir=self.keys_path)

    @property
    def keys_path(self):
        return os.path.join(self.path, ".keys")

    @property
    def credentials(self):
        creds = []
        for root, dirnames, filenames in os.walk(self.path):
            for filename in fnmatch.filter(filenames, '*.pyssword'):
                with open(os.path.join(root, filename)) as f:
                    creds.append(yaml.load(f))
        return creds

    def _credential_path(self, credential):
        return os.path.join(
            self.path,
            credential.name,
            "{}.pyssword".format(credential.login)
        )

    def key_input(self, passphrase):
        return gnupg.GPG().gen_key_input(
            name_real="Pysswords",
            name_email="pysswords@pysswords",
            name_comment="Auto-generated by Pysswords",
            key_length=4096,
            expire_date=0,
            passphrase=passphrase
        )

    def create_keys(self, passphrase):
        return self.gpg.gen_key(self.key_input(passphrase))

    def create_keyring(self, passphrase):
        self.create_keys(self.keys_path, passphrase)
        return self.keys_path


    def add(self, credential):
        cred_path = self._credential_path(credential)
        os.makedirs(os.path.dirname(cred_path))
        with open(cred_path, "w") as f:
            f.write(self.content(credential))
        return cred_path
