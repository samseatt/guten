#!/usr/bin/env python3
"""Decrypt the Admin CloudShell credential handoff locally; never print credentials."""
import argparse
import configparser
import os
from pathlib import Path
from cryptography.hazmat.primitives import serialization,hashes
from cryptography.hazmat.primitives.asymmetric import padding,rsa


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--private-key',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    raw=a.private_key.read_bytes()
    key=(serialization.load_ssh_private_key(raw,password=None) if b'BEGIN OPENSSH PRIVATE KEY' in raw else serialization.load_pem_private_key(raw,password=None))
    if not isinstance(key,rsa.RSAPrivateKey):p.error('RSA Guten key required')
    clear=key.decrypt(a.input.read_bytes(),padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),algorithm=hashes.SHA256(),label=None))
    cfg=configparser.ConfigParser(interpolation=None)
    cfg.read_string(clear.decode())
    if cfg.sections()!=['default'] or set(cfg['default'])!={'aws_access_key_id','aws_secret_access_key'}:
        p.error('Unexpected credential format')
    with os.fdopen(os.open(a.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as stream:stream.write(clear)
    print('Credentials decrypted into the private output file; no secret displayed.')

if __name__=='__main__':main()
