import base64
import sys


def generate_master_key():
    key = b"YourSecretMasterKeyForDevelopmentPurposesOnly"
    encoded = base64.urlsafe_b64encode(key)
    return encoded.decode()


if __name__ == "__main__":
    print(generate_master_key())
