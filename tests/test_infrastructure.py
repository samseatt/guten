"""Safety checks for the fixed bootstrap resource plan; no AWS calls."""
import base64
from pathlib import Path
import struct
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from prepare_infrastructure import template, validate_public_key


def sample_key():
    parts=[b'ssh-rsa',b'\x01\x00\x01',b'\x00\x80'+b'\x01'*511]
    return 'ssh-rsa '+base64.b64encode(b''.join(struct.pack('>I',len(p))+p for p in parts)).decode()


class InfrastructureTests(unittest.TestCase):
    def setUp(self):
        self.key=sample_key()
        self.config=template(self.key,'8.8.8.8/32')

    def test_fixed_resource_count_and_bundles_without_addons(self):
        resources=self.config['Resources']
        self.assertEqual(len(resources),5)
        hosts=[r['Properties'] for r in resources.values() if r['Type']=='AWS::Lightsail::Instance']
        self.assertEqual({h['BundleId'] for h in hosts},{'small_3_0','medium_3_0'})
        self.assertEqual(len(hosts),2)
        self.assertTrue(all(h['BlueprintId']=='ubuntu_24_04' and h['AvailabilityZone']=='us-east-1a' for h in hosts))
        self.assertTrue(all('AddOns' not in h and 'Hardware' not in h for h in hosts))
        self.assertTrue(all(r['Condition']=='ApprovedAccountAndRegion' for r in resources.values()))
        self.assertEqual(resources['ApplicationIp']['Properties']['AttachedTo'],'guten-app-01')
        self.assertEqual(resources['ApplicationIp']['DependsOn'],'ApplicationHost')

    def test_ports_and_no_public_database(self):
        for name,expected in [('ApplicationHost',{22,80,443}),('DatabaseHost',{22})]:
            ports=self.config['Resources'][name]['Properties']['Networking']['Ports']
            self.assertEqual({p['FromPort'] for p in ports},expected)
            ssh=next(p for p in ports if p['FromPort']==22)
            self.assertEqual(ssh['Cidrs'],[{'Ref':'AdminIpv4Cidr'}])
            self.assertEqual(ssh['Ipv6Cidrs'],[])

    def test_bucket_is_private_versioned_and_complete_backups_not_expired(self):
        bucket=self.config['Resources']['BackupBucket']
        properties=bucket['Properties']
        self.assertTrue(all(properties['PublicAccessBlockConfiguration'].values()))
        self.assertEqual(properties['VersioningConfiguration']['Status'],'Enabled')
        self.assertEqual(properties['BucketEncryption']['ServerSideEncryptionConfiguration'][0]['ServerSideEncryptionByDefault']['SSEAlgorithm'],'AES256')
        rules=properties['LifecycleConfiguration']['Rules']
        self.assertTrue(all('ExpirationInDays' not in r and 'NoncurrentVersionExpiration' not in r for r in rules))
        self.assertEqual(bucket['DeletionPolicy'],'RetainExceptOnCreate')
        self.assertEqual(self.config['Resources']['DatabaseHost']['DeletionPolicy'],'RetainExceptOnCreate')
        policy=self.config['Resources']['BackupBucketPolicy']['Properties']['PolicyDocument']['Statement'][0]
        self.assertEqual(policy['Effect'],'Deny')
        self.assertEqual(policy['Condition'],{'Bool':{'aws:SecureTransport':'false'}})

    def test_rejects_wide_or_private_ssh_access_and_invalid_keys(self):
        for cidr in ('0.0.0.0/0','8.8.8.0/24','127.0.0.1/32','10.0.0.1/32'):
            with self.assertRaises(ValueError): template(self.key,cidr)
        for key in ('-----BEGIN PRIVATE KEY-----','ssh-rsa nope',"ssh-rsa AA'$(whoami)"):
            with self.assertRaises(ValueError): validate_public_key(key)

    def test_launch_script_parses_and_does_not_install_or_start_services(self):
        for name in ('ApplicationHost','DatabaseHost'):
            script=self.config['Resources'][name]['Properties']['UserData']['Fn::Sub'].replace('${SshPublicKey}',self.key)
            result=subprocess.run(['sh','-n'],input=script,text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertNotIn('docker',script)
            self.assertNotIn('apt-get',script)

    def test_launch_runs_under_lightsail_sh_wrapper_and_preserves_existing_keys(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name,role in [('ApplicationHost','application'),('DatabaseHost','database')]:
                home=root/name/'home'
                config=root/name/'etc'
                home.mkdir(parents=True)
                authorized=home/'authorized_keys'
                authorized.write_text('existing-default-key\n')
                script=self.config['Resources'][name]['Properties']['UserData']['Fn::Sub'].replace('${SshPublicKey}',self.key)
                script=script.replace('/home/ubuntu/.ssh',str(home)).replace('/etc/guten',str(config))
                # Test without root; ownership commands are the only mocked operations.
                script=script.replace('-o ubuntu -g ubuntu ','').replace('chown ubuntu:ubuntu ',': ')
                wrapped='#!/bin/sh\n# Lightsail initialization precedes user commands.\n'+script
                for _ in range(2):
                    result=subprocess.run(['sh'],input=wrapped,text=True,capture_output=True)
                    self.assertEqual(result.returncode,0,result.stderr)
                self.assertEqual(authorized.read_text().splitlines(),['existing-default-key',self.key])
                self.assertEqual(authorized.stat().st_mode & 0o777,0o600)
                self.assertEqual((config/'host-role').read_text().strip(),role)


class LauncherTests(unittest.TestCase):
    def test_launch_prechecks_and_protected_creation_with_fake_aws(self):
        import json,os,tempfile
        from prepare_infrastructure_launcher import launcher
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            fake=root/'aws'
            fake.write_text('''#!/usr/bin/env python3
import json,os,sys
from pathlib import Path
args=sys.argv[1:]
if args[:2]==['sts','get-caller-identity']: print(os.environ.get('FAKE_ACCOUNT','983732020946'))
elif args[:2]==['cloudformation','describe-stacks']:
 print(os.environ.get('FAKE_STACK_ERROR','Stack with id guten-bootstrap does not exist'),file=sys.stderr);sys.exit(255)
elif args[:2]==['lightsail','get-instances']: print(os.environ.get('FAKE_INSTANCES','0'))
elif args[:2] in (['lightsail','get-static-ips'],['s3api','list-buckets']): print('0')
elif args[:2]==['lightsail','get-bundles']:
 print(json.dumps({'bundles':[{'bundleId':name,'price':float(os.environ.get('FAKE_PRICE',price)),'isActive':True,'ramSizeInGb':ram,'diskSizeInGb':disk,'supportedPlatforms':['LINUX_UNIX']} for name,price,ram,disk in [('small_3_0',12,2,60),('medium_3_0',24,4,80)]]}))
elif args[:2]==['cloudformation','validate-template']: print('Validated')
elif args[:2]==['cloudformation','create-stack']:
 path=args[args.index('--cli-input-json')+1][7:]
 Path(os.environ['CAPTURE']).write_text(Path(path).read_text());print('Fake stack requested')
else: sys.exit('Unexpected AWS call')
''')
            fake.chmod(0o700)
            script=root/'launch.sh'
            script.write_text(launcher(template(sample_key(),'8.8.8.8/32')))
            capture=root/'request.json'
            env=dict(os.environ,PATH=str(root)+os.pathsep+os.environ['PATH'],CAPTURE=str(capture))
            for extra in ({'FAKE_ACCOUNT':'000000000000'},{'FAKE_INSTANCES':'1'},{'FAKE_STACK_ERROR':'AccessDenied'},{'FAKE_PRICE':'99'}):
                result=subprocess.run(['bash',str(script)],env=dict(env,**extra),capture_output=True,text=True)
                self.assertNotEqual(result.returncode,0,result.stderr)
                self.assertFalse(capture.exists())
            result=subprocess.run(['bash',str(script)],env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            request=json.loads(capture.read_text())
            self.assertTrue(request['EnableTerminationProtection'])
            self.assertEqual(request['StackName'],'guten-bootstrap')
            self.assertEqual(len(json.loads(request['TemplateBody'])['Resources']),5)
            policy=json.loads(request['StackPolicyBody'])
            self.assertTrue(any(s['Effect']=='Deny' and 'LogicalResourceId/DatabaseHost' in s['Resource'] for s in policy['Statement']))


if __name__=='__main__': unittest.main()
