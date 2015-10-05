#!/usr/bin/python3
import argparse
import logging
import os
import shutil
import subprocess
import time

import mysql.connector

def port_for_version(version):
    v = version.split('.')
    return int(v[0]) * 1000 + int(v[1]) * 100 + int(v[2])

class mysqlsandbox:
    '''Manage a single MySQL Sandbox'''
    def __init__(self, version, prefix, sbbasedir):
        self.version = version
        self.prefix = prefix
        self.sbbasedir = sbbasedir
        self.datafrom = 'script'

    def provision(self):
        logging.debug('SB Provisioning %s (datafrom: %s)',
                      self.version, self.datafrom)
        subprocess.call(['make_sandbox', self.version,
                         '--add_prefix=%s' % self.prefix,
                         '--', '--no_confirm', '--no_show',
                         '--datadir_from', self.datafrom])

    def deprovision(self):
        logging.debug('SB Deprovisioning %s', self.version) 
        subprocess.call(['sbtool', '-o', 'delete',
                         '--source_dir', self.sbdir])

    @property
    def datadir(self):
        return self.sbdir + '/data'

    @property
    def sbdir(self):
        return os.path.expanduser('{sbbasedir}/msb_{prefix}{version}'.format(
               sbbasedir=self.sbbasedir, prefix=self.prefix,
               version=self.version.replace('.','_')))
      
    def sbcmd(self, cmd):
        cwd = os.getcwd()
        os.chdir(self.sbdir)
        output = subprocess.check_output(cmd)
        os.chdir(cwd)
        return output
 
    def stop(self):
        self.sbcmd('./stop')

    def start(self):
        self.sbcmd('./start')

    def upgrade(self):
        output = self.sbcmd(['./my', 'sql_upgrade', '--skip-verbose'])
        for line in output.decode('utf-8').splitlines():
            if not line.endswith('OK'):
                print(line)


class upgradetest:
    '''Test a upgrades of MySQL with assistance of MySQL Sandbox'''
    versions = ['4.1.21', '5.0.96', '5.1.73', '5.5.45', '5.6.25', '5.7.9']
    prefix = 'ugt'
    sbbasedir = '~/sandboxes'
    ugtdatadir = '/tmp/ugtdatadir'
    sandboxes = {}
    callbacks = {}

    def provision(self, version, datafrom=''):
        logging.debug('UGT Provisioning %s' % version)
        sb = mysqlsandbox(version, prefix=self.prefix,
                          sbbasedir=self.sbbasedir)
        if datafrom:
            sb.datafrom = datafrom
        sb.provision()
        self.sandboxes['version'] = sb
        return sb

    def deprovision(self, version):
        logging.debug('UGT Deprovisioning %s' % version)
        try:
            self.sandboxes['version'].deprovision()
        except KeyError:
            logging.warning("Trying to deprovision non-registerd sandbox %s" 
                            % version)
            sb = mysqlsandbox(version, prefix=self.prefix,
                              sbbasedir=self.sbbasedir)
            sb.deprovision()

    def cleanup(self):
        for version in self.versions:
            self.deprovision(version)
        self.rmugtdatadir()

    def rmugtdatadir(self):
        try:
            shutil.rmtree(self.ugtdatadir)
        except FileNotFoundError:
            logging.warning('Can\'t remove non-existing ugtdatadir')

    def runtest(self):
        initial = True
        for version in self.versions:
            if initial is True:
                sb = ugt.provision(version)
                initial = False
            else:
                sb = ugt.provision(version, datafrom='dir:/tmp/ugtdatadir')
            sb.start()
            self.runcb(version, 'preupgrade')
            sb.upgrade()
            self.runcb(version, 'postupgrade')
            sb.stop()
            self.rmugtdatadir()
            shutil.copytree(sb.datadir, '/tmp/ugtdatadir')

    def registercb(self, version, event, fn):
        '''Register Callback'''

        if not version in self.callbacks:
            self.callbacks[version] = {}
            if not event in self.callbacks[version]:
                self.callbacks[version][event] = []
        self.callbacks[version][event].append(fn)

    def runcb(self, version, event):
        '''Run a callback function'''

        if version in self.callbacks:
            if event in self.callbacks[version]:
                cnconfig = { 'host': '127.0.0.1', 'port': port_for_version(version),
                             'user': 'root', 'password': 'msandbox',
                             'database': 'test', 'get_warnings': True}
                logging.debug('Running callback for %s event for version %s' 
                              % (event, version))
                for cb in self.callbacks[version][event]:
                    cb(cnconfig)

def ugtcb(description, sql):
    '''Upgrade Test Call Back
    this is a template for simple callbacks, which just run some sql
    '''
    def ugtcb_closure(cnconfig):
        logging.info('Callback Description: {desc}'.format(desc=description))
        con = mysql.connector.connect(**cnconfig)
        cur = con.cursor()
        logging.debug('Callback SQL: {sql}'.format(sql=sql))
        for result in cur.execute(sql, multi=True):
            pass
        con.commit()  # Not needed because implicit commit of DDL
        cur.close()
        con.close()
    return ugtcb_closure

cb_41_myisam = ugtcb('Creating MyISAM table on 4.1',
    '''CREATE TABLE t_41_myisam1 (
id int auto_increment, name VARCHAR(255),
poi GEOMETRY NOT NULL,
info TEXT,
FULLTEXT KEY(info),
SPATIAL KEY(poi),
PRIMARY KEY (id)) ENGINE=MyISAM''')

cb_41_ib = ugtcb('Creating t_41_ib1 with InnoDB on 4.1',
    '''CREATE TABLE t_41_ib1 (
id int auto_increment, name VARCHAR(255),
PRIMARY KEY (id)) ENGINE=InnoDB''')

cb_51_par = ugtcb('Creating t_51_par1 with partitioning on 5.1',
    '''CREATE TABLE t_51_par1 (
id int auto_increment, name TEXT,
PRIMARY KEY (id)) ENGINE=InnoDB PARTITION BY KEY(id) PARTITIONS 5''')

cb_55_ug_par = ugtcb('Upgrading t_51_par1 with partitioning on 5.5',
    '''ALTER TABLE `test`.`t_51_par1`
PARTITION BY KEY /*!50531 ALGORITHM = 1 */ (id) PARTITIONS 5''')

cb_55_cmp = ugtcb('Creating t_55_cmp1 with compression on 5.5',
    '''SET GLOBAL innodb_file_format=Barracuda;
SET GLOBAL innodb_file_per_table=1;
CREATE TABLE t_55_cmp1 (
id int auto_increment, name TEXT,
PRIMARY KEY (id)) ENGINE=InnoDB ROW_FORMAT=COMPRESSED''')

cb_56_ft = ugtcb('Creating t_56_ft1 with fulltext index on 5.6',
    '''CREATE TABLE t_56_ft1 (
id int auto_increment, name TEXT,
FULLTEXT KEY `ft_name` (name),
PRIMARY KEY (id))''')

cb_57_rt = ugtcb('Creating t_57_rt1 with spatial index on 5.7',
    '''CREATE TABLE t_57_rt1 (
id int auto_increment, poi GEOMETRY NOT NULL,
SPATIAL KEY `rt_poi` (poi),
PRIMARY KEY (id))''')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', action="store_true", help="Enable debug output")
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    ugt = upgradetest()
    ugt.cleanup()
    ugt.registercb('4.1.21', 'postupgrade', cb_41_myisam)
    ugt.registercb('4.1.21', 'postupgrade', cb_41_ib)
    ugt.registercb('5.1.73', 'postupgrade', cb_51_par)
    ugt.registercb('5.5.45', 'postupgrade', cb_55_ug_par)
    ugt.registercb('5.5.45', 'postupgrade', cb_55_cmp)
    ugt.registercb('5.6.25', 'postupgrade', cb_56_ft)
    ugt.registercb('5.7.9', 'postupgrade', cb_57_rt)
    ugt.runtest()
