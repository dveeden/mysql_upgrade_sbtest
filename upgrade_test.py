#!/usr/bin/python3
import os
import shutil
import time
import logging
import subprocess

import mysql.connector

class mysqlsandbox:
    def __init__(self, version, prefix, sbbasedir):
        self.version = version
        self.prefix = prefix
        self.sbbasedir = sbbasedir
        self.datafrom = 'script'

    def provision(self):
        logging.debug('SB Provisioning %s (datafrom: %s)' % 
                       (self.version, self.datafrom))
        subprocess.call(['make_sandbox', self.version,
                         '--add_prefix=%s' % self.prefix,
                         '--', '--no_confirm', '--no_show',
                         '--datadir_from', self.datafrom])

    def deprovision(self):
        logging.debug('SB Deprovisioning %s' % self.version) 
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
        subprocess.call(cmd)
        os.chdir(cwd)
 
    def stop(self):
        self.sbcmd('./stop')

    def start(self):
        self.sbcmd('./start')

    def upgrade(self):
        self.sbcmd(['./my', 'sql_upgrade', '--skip-verbose'])


class upgradetest:
    versions = ['5.0.96', '5.1.73', '5.5.45', '5.6.25', '5.7.9']
    prefix = 'ugt'
    sbbasedir = '~/sandboxes'
    ugtdatadir = '/tmp/ugtdatadir'
    sandboxes = {}

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
        sb = ugt.provision(self.versions[0])
        input('Please load your data and press any key to continue')
        sb.stop()
        shutil.copytree(sb.datadir, '/tmp/ugtdatadir')

        for version in self.versions[1:]:
            sb = ugt.provision(version, datafrom='dir:/tmp/ugtdatadir')
            sb.start()
            sb.upgrade()
            sb.stop()
            self.rmugtdatadir()
            shutil.copytree(sb.datadir, '/tmp/ugtdatadir')
  

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)

    ugt = upgradetest()
    ugt.cleanup()
    ugt.runtest()
