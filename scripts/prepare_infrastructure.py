#!/usr/bin/env python3
"""Generate a fixed-cost Lightsail/S3 CloudFormation template; never calls AWS."""
import argparse
import base64
import ipaddress
import json
from pathlib import Path
import struct

ACCOUNT='983732020946'
REGION='us-east-1'


def validate_public_key(value):
    fields=value.strip().split()
    if len(fields)<2 or fields[0]!='ssh-rsa':
        raise ValueError('Use an OpenSSH RSA public key (.pub), never a private key.')
    try:
        data=base64.b64decode(fields[1],validate=True)
        values=[]
        while data:
            size=struct.unpack('>I',data[:4])[0]
            if size>len(data)-4: raise ValueError()
            values.append(data[4:4+size]);data=data[4+size:]
        if len(values)!=3 or values[0]!=b'ssh-rsa' or int.from_bytes(values[2],'big').bit_length()<3072:
            raise ValueError()
    except Exception:
        raise ValueError('Expected an RSA public key of at least 3072 bits.') from None
    return ' '.join(fields[:2])


def template(public_key, admin_cidr):
    key=validate_public_key(public_key)
    network=ipaddress.IPv4Network(admin_cidr,strict=True)
    if network.prefixlen!=32 or not network.network_address.is_global:
        raise ValueError('SSH must be restricted to one public IPv4 address (/32).')
    tag=[{'Key':'Project','Value':'Guten'},{'Key':'Environment','Value':'bootstrap'}]
    ssh={'FromPort':22,'ToPort':22,'Protocol':'tcp','Cidrs':[{'Ref':'AdminIpv4Cidr'}],'Ipv6Cidrs':[]}
    web=[{'FromPort':p,'ToPort':p,'Protocol':'tcp','Cidrs':['0.0.0.0/0'],'Ipv6Cidrs':[]} for p in (80,443)]
    resources={}
    for logical,name,bundle,role in [('ApplicationHost','guten-app-01','medium_3_0','application'),('DatabaseHost','guten-db-01','small_3_0','database')]:
        # No Docker or database starts here. The next phase establishes host
        # forwarding rules and verified TLS before any database port is published.
        launch='''#!/bin/bash
set -euo pipefail
install -d -m 700 -o ubuntu -g ubuntu /home/ubuntu/.ssh
key='${SshPublicKey}'
touch /home/ubuntu/.ssh/authorized_keys
if ! grep -qxF "$key" /home/ubuntu/.ssh/authorized_keys; then
  printf '%s\\n' "$key" >> /home/ubuntu/.ssh/authorized_keys
fi
chown ubuntu:ubuntu /home/ubuntu/.ssh/authorized_keys
chmod 600 /home/ubuntu/.ssh/authorized_keys
install -d -m 755 /etc/guten
printf '%s\\n' 'ROLE_VALUE' > /etc/guten/host-role
printf '%s\\n' 'SSH key installed; host software and application setup pending.' > /etc/guten/bootstrap-status
'''.replace('ROLE_VALUE',role)
        resources[logical]={
            'Type':'AWS::Lightsail::Instance','Condition':'ApprovedAccountAndRegion','DependsOn':'BackupBucketPolicy',
            'DeletionPolicy':'RetainExceptOnCreate' if role=='database' else 'Delete',
            'UpdateReplacePolicy':'Retain' if role=='database' else 'Delete',
            'Properties':{'InstanceName':name,'AvailabilityZone':'us-east-1a','BlueprintId':'ubuntu_24_04','BundleId':bundle,'Networking':{'Ports':[ssh,*web] if role=='application' else [ssh]},'Tags':tag+[{'Key':'Role','Value':role}],'UserData':{'Fn::Sub':launch}},
        }
    resources['ApplicationIp']={'Type':'AWS::Lightsail::StaticIp','Condition':'ApprovedAccountAndRegion','Properties':{'StaticIpName':'guten-app-ip','AttachedTo':'guten-app-01'},'DependsOn':'ApplicationHost'}
    resources['BackupBucket']={
        'Type':'AWS::S3::Bucket','Condition':'ApprovedAccountAndRegion','DeletionPolicy':'RetainExceptOnCreate','UpdateReplacePolicy':'Retain',
        'Properties':{'BucketName':'guten-backups-983732020946-us-east-1',
            'PublicAccessBlockConfiguration':{'BlockPublicAcls':True,'IgnorePublicAcls':True,'BlockPublicPolicy':True,'RestrictPublicBuckets':True},
            'OwnershipControls':{'Rules':[{'ObjectOwnership':'BucketOwnerEnforced'}]},
            'BucketEncryption':{'ServerSideEncryptionConfiguration':[{'ServerSideEncryptionByDefault':{'SSEAlgorithm':'AES256'}}]},
            'VersioningConfiguration':{'Status':'Enabled'},
            'LifecycleConfiguration':{'Rules':[{'Id':'AbortIncompleteMultipartUploads','Status':'Enabled','AbortIncompleteMultipartUpload':{'DaysAfterInitiation':7}}]},
            'Tags':tag,
        },
    }
    resources['BackupBucketPolicy']={
        'Type':'AWS::S3::BucketPolicy','Condition':'ApprovedAccountAndRegion','DeletionPolicy':'RetainExceptOnCreate','UpdateReplacePolicy':'Retain',
        'Properties':{'Bucket':{'Ref':'BackupBucket'},'PolicyDocument':{'Version':'2012-10-17','Statement':[{'Sid':'RequireTLS','Effect':'Deny','Principal':'*','Action':'s3:*','Resource':[{'Fn::GetAtt':['BackupBucket','Arn']},{'Fn::Sub':'${BackupBucket.Arn}/*'}],'Condition':{'Bool':{'aws:SecureTransport':'false'}}}]}},
    }
    outputs={name:{'Condition':'ApprovedAccountAndRegion','Value':{'Fn::GetAtt':value}} for name,value in {
        'ApplicationPublicIp':['ApplicationIp','IpAddress'], 'ApplicationPrivateIp':['ApplicationHost','PrivateIpAddress'],
        'DatabasePublicIp':['DatabaseHost','PublicIpAddress'],'DatabasePrivateIp':['DatabaseHost','PrivateIpAddress'],
    }.items()}
    outputs['BackupBucketName']={'Condition':'ApprovedAccountAndRegion','Value':{'Ref':'BackupBucket'}}
    outputs['DeploymentGuard']={'Value':{'Fn::If':['ApprovedAccountAndRegion','Approved account and region. Resources requested.','WRONG ACCOUNT OR REGION: no resources requested.']}}
    return {
        'AWSTemplateFormatVersion':'2010-09-09',
        'Description':'Guten bootstrap: exactly two Ubuntu Lightsail hosts (USD 36/month combined), one attached static IP and one private versioned S3 backup bucket. Usage/tax extra. No app/database software started.',
        'Parameters':{
            'AdminIpv4Cidr':{'Type':'String','Default':str(network),'AllowedPattern':r'^(?:[0-9]{1,3}\.){3}[0-9]{1,3}/32$','Description':'Your current public IPv4 /32 for SSH only. HTTP/HTTPS are public on the app host.'},
            'SshPublicKey':{'Type':'String','Default':key,'AllowedPattern':r'^ssh-rsa [A-Za-z0-9+/=]+$','Description':'Public RSA key only. The private key stays on your Mac.'},
        },
        'Conditions':{'ApprovedAccountAndRegion':{'Fn::And':[{'Fn::Equals':[{'Ref':'AWS::AccountId'},ACCOUNT]},{'Fn::Equals':[{'Ref':'AWS::Region'},REGION]}]}},
        'Resources':resources,'Outputs':outputs,
    }


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--public-key',type=Path,required=True)
    p.add_argument('--admin-ip',required=True,help='Current public IPv4 address with /32 suffix.')
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    generated=template(a.public_key.read_text(),a.admin_ip)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x') as stream: json.dump(generated,stream,indent=2);stream.write('\n')
    print(a.output)
