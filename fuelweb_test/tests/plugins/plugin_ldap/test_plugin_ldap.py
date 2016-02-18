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
import os

from proboscis.asserts import assert_true
from proboscis import test

from fuelweb_test import logger
from fuelweb_test import settings as conf
from fuelweb_test.helpers import checkers
from fuelweb_test.helpers.decorators import log_snapshot_after_test
from fuelweb_test.tests.base_test_case import SetupEnvironment
from fuelweb_test.tests.base_test_case import TestBasic
from fuelweb_test.tests.base_test_tempest import TempestTestBase


@test(groups=["plugins"])
class TestLdapPlugin(TestBasic):
    """Class for testing the LDAP plugin."""

    def install_plugin(self):
        logger.info('Started plugin installation procedure.')
        if conf.LDAP_PLUGIN_PATH:
            # copy plugin to the master node
            logger.info("Copying LDAP plugin")
            checkers.upload_tarball(
                self.env.d_env.get_admin_remote(),
                conf.LDAP_PLUGIN_PATH, '/var')

            # install plugin
            logger.info("LDAP plugin installation")
            checkers.install_plugin_check_code(
                self.env.d_env.get_admin_remote(),
                plugin=os.path.basename(conf.LDAP_PLUGIN_PATH))

    @test(depends_on=[SetupEnvironment.prepare_slaves_3],
          groups=["deploy_ldap"])
    @log_snapshot_after_test
    def deploy_ldap(self):
        """Deploy cluster with the LDAP plugin

        Scenario:
            1. Upload LDAP plugin to the master node
            2. Install plugin
            3. Create cluster
            4. Add 1 node with controller role
            5. Add 2 nodes with compute + cinder role
            8. Deploy the cluster
            9. Run OSTF
            10. Run tempest.api.identity tests

        Duration 70m
        Snapshot deploy_ldap

        """
        self.env.revert_snapshot("ready_with_3_slaves")
        self.install_plugin()
        data = {
            "net_provider": 'neutron',
            "net_segment_type": conf.NEUTRON_SEGMENT['tun'],
            'tenant': 'simpleTun',
            'user': 'simpleTun',
            'password': 'simpleTun'
        }
        cluster_id = self.fuel_web.create_cluster(
            name=self.__class__.__name__,
            mode=conf.DEPLOYMENT_MODE,
            settings=data
        )
        logger.info("Check LDAP plugin exists")
        plugin_name = 'ldap'
        msg = "Plugin couldn't be enabled. Check plugin version. Test aborted"
        assert_true(self.fuel_web.check_plugin_exists(cluster_id, plugin_name),
                    msg)
        self.fuel_web.update_nodes(
            cluster_id,
            {
                'slave-01': ['controller'],
                'slave-02': ['compute', 'cinder'],
                'slave-03': ['compute', 'cinder']
            }
        )

        data = {
            "domain": {
                "value": conf.LDAP_DOMAIN
            },
            "url": {
                "value": conf.LDAP_URL
            },
            "user": {
                "value": conf.LDAP_USER
            },
            "query_scope": {
                "value": conf.LDAP_QUERY_SCOPE
            },
            "user_tree_dn": {
                "value": conf.LDAP_USERS_TREE_DN
            },
            "group_tree_dn": {
                "value": conf.LDAP_GROUPS_TREE_DN
            },
            "password": {
                    "value": conf.LDAP_USER_PASSWORD
                },
            "suffix": {
                "value": conf.LDAP_SUFFIX
            }
        }

        self.fuel_web.update_plugin_data(cluster_id, plugin_name, data)

        self.fuel_web.deploy_cluster_wait(cluster_id)

        # logger.info("Run OSTF...")
        # self.fuel_web.run_ostf(cluster_id=cluster_id)
        #
        # # Run tempest api identity tests
        # tempest = TempestTestBase()
        # tempest.install_tempest()
        # tempest.run_tempest(test_suite="tempest.api.identity")

        self.env.make_snapshot("deploy_ldap")



