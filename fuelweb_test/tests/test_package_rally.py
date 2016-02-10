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

from proboscis.asserts import assert_equal
from proboscis import test

from fuelweb_test.helpers import os_actions
from fuelweb_test.helpers.decorators import log_snapshot_after_test
from fuelweb_test.settings import DEPLOYMENT_MODE
from fuelweb_test.settings import NEUTRON_SEGMENT
from fuelweb_test.tests.base_test_case import SetupEnvironment
from fuelweb_test.tests.base_test_case import TestBasic
from fuelweb_test import logger
from fuelweb_test import settings
from fuelweb_test.helpers.rally import RallyBenchmarkTest


@test(groups=["package_rally"])
class PackageRally(TestBasic):
    """PackageRally."""  # TODO documentation

    @test(depends_on=[SetupEnvironment.prepare_slaves_3],
          groups=["deploy_package_rally"])
    @log_snapshot_after_test
    def deploy_package_rally(self):
        """Deploy cluster in ha mode with 1 controller and Neutron VXLAN

        Scenario:
            1. Create cluster
            2. Add 1 node with controller role
            3. Add 2 nodes with compute role
            4. Run network verification
            5. Deploy the cluster
            6. Run network verification
            7. Run Rally benchmark scenario

        Duration 35m
        Snapshot deploy_package_rally

        """
        self.env.revert_snapshot("ready_with_3_slaves")

        data = {
            "net_provider": 'neutron',
            "net_segment_type": NEUTRON_SEGMENT['tun'],
            'tenant': 'simpleTun',
            'user': 'simpleTun',
            'password': 'simpleTun'
        }
        cluster_id = self.fuel_web.create_cluster(
            name=self.__class__.__name__,
            mode=DEPLOYMENT_MODE,
            settings=data
        )
        self.fuel_web.update_nodes(
            cluster_id,
            {
                'slave-01': ['controller'],
                'slave-02': ['compute', 'cinder'],
                'slave-03': ['compute', 'cinder']
            }
        )
        self.fuel_web.update_internal_network(cluster_id, '192.168.196.0/26',
                                              '192.168.196.1')
        self.fuel_web.verify_network(cluster_id)
        self.fuel_web.deploy_cluster_wait(cluster_id)
        os_conn = os_actions.OpenStackActions(
            self.fuel_web.get_public_vip(cluster_id),
            data['user'], data['password'], data['tenant'])

        cluster = self.fuel_web.client.get_cluster(cluster_id)
        assert_equal(str(cluster['net_provider']), 'neutron')
        self.fuel_web.check_fixed_network_cidr(
            cluster_id, os_conn)

        self.fuel_web.verify_network(cluster_id)

        # Run Rally benchmark
        rally_benchmarks = {}
        for tag in set(settings.RALLY_TAGS):
            rally_benchmarks[tag] = RallyBenchmarkTest(
                container_repo=settings.RALLY_DOCKER_REPO,
                environment=self.env,
                cluster_id=cluster_id,
                test_type=tag
            )
            logger.info("Run Rally benchmark for tag: {0}".format(tag))
            rally_benchmarks[tag].run()

        # Copy files from rally container directory
        remote = self.env.d_env.get_admin_remote()
        rally_directory = '/var/rally-{0}/'.format(cluster_id)
        list_of_files = remote.execute('ls {0}'.format(rally_directory))['stdout']

        for file in list_of_files:
            file = file.replace('\n', '')
            full_file_path = rally_directory + file
            logger.info('Copying file ' + file)
            remote.download(full_file_path, 'logs/')

        self.env.make_snapshot("deploy_package_rally")

