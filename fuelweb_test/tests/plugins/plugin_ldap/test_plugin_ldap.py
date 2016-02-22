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
import json
import os

from proboscis.asserts import assert_true
from proboscis.asserts import assert_equal
from proboscis.asserts import assert_is_not_none
from proboscis import test

from fuelweb_test import logger
from fuelweb_test import settings as conf
from fuelweb_test.helpers import checkers
from fuelweb_test.helpers.decorators import log_snapshot_after_test
from fuelweb_test.tests.base_test_case import SetupEnvironment
from fuelweb_test.tests.base_test_case import TestBasic
import requests

@test(groups=["plugins"])
class TestLdapPlugin(TestBasic):
    """Class for testing the LDAP plugin."""

    def get_dashboard_url(self):
        with self.env.d_env.get_admin_remote() as remote:
            cmd = "fuel node \"$@\" | grep controller | awk '{print $1}' | head -1"
            controller_host_id = remote.execute(cmd)['stdout'][0].strip()
            controller_host = "node-{0}".format(controller_host_id)
            cmd = "ssh %s \"grep public_vip /etc/hiera/globals.yaml | awk '{print \$2}' \"" % controller_host
            public_ip = remote.execute(cmd)['stdout'][0].strip()[1:-1]
        return public_ip

    def get_user(self):
        for param in conf.LDAP_USER.split(','):
            if param.startswith("cn="):
                user = param[3:].strip()
                return user

    def check_get_token(self):
        dashboard_url = self.get_dashboard_url()
        user = self.get_user()
        self.session = requests.Session()

        data = {
            "auth": {
                "identity": {
                    "methods": [
                        "password"
                    ],
                    "password": {
                        "user": {
                            "name": user,
                            "password": conf.LDAP_USER_PASSWORD,
                            "domain": {
                                "name": conf.LDAP_DOMAIN
                            }
                        }
                    }
                }
            }
        }
        self.session.headers.update({'Content-Type': 'application/json'})
        resp = requests.post(
            'https://{0}:5000/v3/auth/tokens'.format(dashboard_url),
            data=json.dumps(data), headers=self.session.headers, verify=False)
        assert_equal(
            resp.status_code, 201,
            message="Unexpected status code: {}".format(resp.status_code))
        assert_is_not_none(
            resp.headers['X-Subject-Token'],
            message="Unexpected error: X-Subject-Token is {}".
                    format(resp.headers['X-Subject-Token']))
        assert_is_not_none(
            json.loads(resp.text)['token']['user'],
            message="Unexpected error in the body of response: ['token']"
                    "['user'] is {0}".format(
                json.loads(resp.text)['token']['user']))

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
            10. Check LDAP user can authorize

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
            },
            "user_objectclass": {
                "value": conf.LDAP_USER_OBJECT_CLASS
            },
            "user_name_attribute": {
                "value": conf.LDAP_USER_NAME_ATTRIBUTE
            }
        }
        self.fuel_web.update_plugin_data(cluster_id, plugin_name, data)

        options = {'metadata/enabled': True}
        self.fuel_web.update_plugin_data(cluster_id, plugin_name, options)

        self.fuel_web.deploy_cluster_wait(cluster_id)

        logger.info("Run OSTF...")
        # self.fuel_web.run_ostf(cluster_id=cluster_id)

        logger.info("Checking get token request for LDAP user...")
        # self.check_get_token()

        self.env.make_snapshot("deploy_ldap")


