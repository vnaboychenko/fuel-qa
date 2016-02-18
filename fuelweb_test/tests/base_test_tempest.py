#    Copyright 2016 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from fuelweb_test.tests.base_test_case import TestBasic
from fuelweb_test import logger


class TempestTestBase(TestBasic):

    def install_tempest(self):
        with self.env.d_env.get_admin_remote() as remote:
            test_suite = "[7.0][MOSQA] Automated Cloud Testing"
            mos_repository = "https://github.com/Mirantis/"
            tests_folder = "mos-tempest-runner"
            branch = "stable/7.0"
            prepeare_cmd = ("export TESTRAIL_SUITE='{0}' &&"
                   "yum install git -y && git clone {1}{2} -b {3} &&"
                   "cd {2} && ./setup_env.sh".format(test_suite, mos_repository, tests_folder, branch))

            logger.info("Run Tempest installation")
            prepeare_result = remote.execute(prepeare_cmd)

            for line in prepeare_result['stdout']:
                logger.info(line)

    def run_tempest(self, test_suite=""):
        # test_suite (str): default "" means run all tests
        # example: test_suite="tempest.api.identity"

        with self.env.d_env.get_admin_remote() as remote:
            logger.info("Run Tempest tests")
            run_tempest_cmd = ("source /home/developer/mos-tempest-runner/."
                               "venv/bin/activate "
                               "&& pip install -U oslo.config"
                               "&& source /home/developer/openrc"
                               "&& run_tests {0}".format(test_suite))
            run_tempest_result = remote.execute(run_tempest_cmd)

            # Tempest test reports store in stderr Array
            for line in run_tempest_result['stderr']:
                logger.info(line)
            fuel_log_directory='/home/developer/mos-tempest-runner/' \
                               'tempest-reports/'
            list_of_files = remote.execute('ls {0}'.format(
                fuel_log_directory))['stdout']

            for file in list_of_files:
                file = file.replace('\n', '')
                full_file_path = fuel_log_directory + file
                logger.info('Copying file ' + file )
                remote.download(full_file_path, 'logs/')


