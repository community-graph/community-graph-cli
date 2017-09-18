from base64 import b64decode
from base64 import b64encode

import boto3


def decrypt_value(encrypted):
    return boto3.client('kms').decrypt(CiphertextBlob=b64decode(encrypted))['Plaintext'].decode("utf-8")


def encrypt_value(value, kms_key):
    return b64encode(boto3.client('kms').encrypt(Plaintext=value, KeyId=kms_key)["CiphertextBlob"])
