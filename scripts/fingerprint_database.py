#!/usr/bin/env python3
"""Read-only content, sequence and constraint fingerprint using a supplied psql command."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def fingerprint(command, database):
    def query(statement):
        return subprocess.check_output([*command, '-X', '-q', '-A', '-t', '-v', 'ON_ERROR_STOP=1', '-d', database, '-c', 'BEGIN READ ONLY', '-c', "SET LOCAL TIME ZONE 'UTC'", '-c', statement, '-c', 'COMMIT'], text=True)
    def identifier(value):
        return '"'+value.replace('"','""')+'"'
    result={'tables':{},'sequences':{}}
    # Each query is read-only; compare only while content edits are paused.
    tables=json.loads(query("SELECT coalesce(json_agg(t),'[]') FROM (SELECT schemaname,tablename FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema') ORDER BY 1,2) t"))
    for row in tables:
        schema,table=row['schemaname'],row['tablename']
        text=query(f'SELECT to_jsonb(t)::text FROM {identifier(schema)}.{identifier(table)} t ORDER BY to_jsonb(t)::text COLLATE "C"')
        result['tables'][schema+'.'+table]={'rows':len(text.splitlines()),'sha256':hashlib.sha256(text.encode()).hexdigest()}
    sequences=json.loads(query("SELECT coalesce(json_agg(t),'[]') FROM (SELECT schemaname,sequencename FROM pg_sequences WHERE schemaname NOT IN ('pg_catalog','information_schema') ORDER BY 1,2) t"))
    for row in sequences:
        schema,sequence=row['schemaname'],row['sequencename']
        result['sequences'][schema+'.'+sequence]=json.loads(query(f'SELECT json_build_array(last_value,is_called) FROM {identifier(schema)}.{identifier(sequence)}'))
    result['constraints']=json.loads(query("SELECT coalesce(json_agg(json_build_array(nspname,relname,conname,definition)),'[]') FROM (SELECT n.nspname,c.relname,x.conname,pg_get_constraintdef(x.oid) definition FROM pg_constraint x JOIN pg_class c ON c.oid=x.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname NOT IN ('pg_catalog','information_schema') ORDER BY 1,2,3) t"))
    result['columns']=json.loads(query("SELECT coalesce(json_agg(t),'[]') FROM (SELECT n.nspname,c.relname,a.attname,a.attnum,format_type(a.atttypid,a.atttypmod) data_type,a.attnotnull,a.attidentity,a.attgenerated,pg_get_expr(d.adbin,d.adrelid) default_expression FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum WHERE c.relkind IN ('r','p','v') AND a.attnum>0 AND NOT a.attisdropped AND n.nspname NOT IN ('pg_catalog','information_schema') ORDER BY 1,2,4) t"))
    result['indexes']=json.loads(query("SELECT coalesce(json_agg(t),'[]') FROM (SELECT schemaname,tablename,indexname,indexdef FROM pg_indexes WHERE schemaname NOT IN ('pg_catalog','information_schema') ORDER BY 1,2,3) t"))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--database',required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--psql-command',nargs=argparse.REMAINDER,default=['psql'],help='Last option; command prefix ending in psql')
    a=p.parse_args()
    result=fingerprint(a.psql_command,a.database)
    with a.output.open('x') as stream:
        json.dump(result,stream,indent=2); stream.write('\n')
    print(f'Fingerprinted {len(result["tables"])} tables and {len(result["sequences"])} sequences.')
